"""Deteccion de fijos: cuando el usuario captura algo que ya es un fijo.

Por que hace falta: los fijos se declaran a mano (Movimientos › Fijos) y tambien se capturan.
El problema aparece en el choque entre los dos. El usuario ya declaro "Arriendo,
1.200.000, dia 5" y captura "pagué el arriendo". Si la app no dice nada, el
movimiento queda huerfano del fijo. Si crea un fijo nuevo, el usuario termina con
dos "Arriendo" y el motor los cuenta doble en el ratio de gasto fijo.

La respuesta correcta no es adivinar: es PREGUNTAR. "¿Es el mismo arriendo o uno
distinto?" El usuario sabe, la app no.

Que la app detects bien es lo que hace util la pregunta; que la detecte mal es lo
que la vuelve molesta. Por eso el umbral es alto y se puede rechazar de un toque.

Por que no se hace con el modelo de lenguaje: comparar "pagué el arriendo de este
mes" con "Arriendo" no necesita un LLM, y un LLM seria mas caro, mas lento y
menos determinista. Ademas el motor ya tiene las tools del asesor; esto es
comparacion de texto y numeros, y sale mas barato a mano.
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.finance import Transaction
from app.models.goals import Recurring
from app.services import recurrencia as recu

# Cuanto puede moverse el monto y seguir siendo "el mismo fijo".
# El arriendo sube 50.000 al ano y eso no es un fijo nuevo, es el mismo.
TOLERANCIA_MONTO = 0.12
# Confianza minima para preguntar. Si esta abajo, mejor callarse: molestar con
# una coincidencia mala hace que el usuario deje de mirar las preguntas.
CONFIANZA_MINIMA = 0.55

# Palabras que no distinguen un gasto de otro. Sirven para saber que dos textos
# NO se parecen, no para construir parecido.
_RUIDO = {"de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
          "por", "para", "con", "en", "y", "o", "a", "al", "mis", "mi", "este",
          "esta", "este mes", "mes", "hoy", "ayer", "pago", "pague", "pagada",
          "pago de", "gasto", "gaste", "compra", "compre", "nuevo", "nueva"}


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", t)


def _tokens(texto: str) -> set[str]:
    return {t for t in _normalizar(texto).split() if t and t not in _RUIDO}


def _parecido_nombre(a: str, b: str) -> float:
    """Similitud entre el texto capturado y el nombre del fijo, de 0 a 1.

    Se comparan PALABRAS y no caracteres: "arriendo" contra "pago de arriendo"
    tiene que dar parecido alto, y "arriendo" contra "internet" cero. Comparar
    caracteres de entrada daria 0.6 para cosas que no tienen nada que ver
    ("arriendo" y "arriendo old" se parecen mas a "salario" de lo que parece).
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    comunes = ta & tb
    if not comunes:
        return 0.0
    # Jaccard: comunes sobre todo lo que hay entre los dos.
    return len(comunes) / len(ta | tb)


def _parecido_monto(fijo: float, movimiento: float) -> float:
    """1.0 si son iguales, bajando segun cuanto se diferencien."""
    fijo, movimiento = abs(float(fijo)), abs(float(movimiento))
    if movimiento <= 0:
        return 0.0
    dif = abs(fijo - movimiento) / movimiento
    if dif <= TOLERANCIA_MONTO:
        return 1.0 - (dif / TOLERANCIA_MONTO) * 0.3   # dentro del rango: 0.7 a 1.0
    # Fuera del rango: sigue habiendo parecido, pero decays.
    return max(0.0, 0.5 - (dif - TOLERANCIA_MONTO) / 2)


def _parecido_dia(fijo_dia: int, mov_dia: int) -> float:
    """El dia del mes tambien dice algo: un arriendo es el dia 5, no el 28."""
    d = abs(int(fijo_dia) - int(mov_dia))
    if d == 0:
        return 1.0
    if d <= 2:
        return 0.8
    if d <= 5:
        return 0.5
    return 0.0


def _confianza(nombre: float, monto: float, dia: float, pesos: dict) -> float:
    return (nombre * pesos["nombre"] + monto * pesos["monto"] + dia * pesos["dia"]
            ) / sum(pesos.values())


def detectar(db: Session, user_id: str, perfil_id: str, descripcion: str,
             tipo: str, monto: float, dia: int,
             pesos: dict | None = None) -> list[dict]:
    """Fijos que podrian ser este movimiento, de mas probable a menos.

    No adivina un "es el mismo": devuelve candidatos con su confianza para que
    la UI pregunte. Un solo candidato por encima del umbral es un caso claro;
    varios significan que hay que preguntar cual.
    """
    pesos = pesos or {"nombre": 0.5, "monto": 0.35, "dia": 0.15}
    candidatos = []
    for r in db.query(Recurring).filter_by(user_id=user_id, perfil_id=perfil_id,
                                           activo=True).all():
        if r.tipo != tipo:
            # Un ingreso nunca es el mismo fijo que un gasto, aunque coincida el
            # nombre: "Salario" de ingreso y "Salario" de gasto no son lo mismo.
            continue
        p_nombre = _parecido_nombre(descripcion, r.nombre)
        if p_nombre <= 0:
            continue                      # ni una palabra en comun: ni intentar
        p_monto = _parecido_monto(r.monto, monto)
        p_dia = _parecido_dia(r.dia, dia)
        conf = _confianza(p_nombre, p_monto, p_dia, pesos)
        if conf < CONFIANZA_MINIMA:
            continue
        candidatos.append({
            "id": r.id, "nombre": r.nombre, "tipo": r.tipo,
            "monto": round(float(r.monto), 2), "dia": r.dia,
            "dia_semana": r.dia_semana,
            "etiqueta": recu.etiqueta(r.frecuencia, r.dia, r.dia_semana),
            "frecuencia": r.frecuencia,
            "confianza": round(conf, 2),
            "motivo": _motivo(p_nombre, p_monto, p_dia),
        })
    candidatos.sort(key=lambda c: -c["confianza"])
    return candidatos


def _motivo(nombre: float, monto: float, dia: float) -> str:
    """Por que cree que es el mismo. Sin esto la pregunta es misteriosa."""
    partes = []
    if nombre >= 0.6:
        partes.append("el nombre se parece")
    if monto >= 0.7:
        partes.append("el monto es casi igual")
    elif monto >= 0.4:
        partes.append("el monto se acerca")
    if dia >= 0.8:
        partes.append("cayo el mismo dia de siempre")
    return ", ".join(partes) or "se parece en algo"


def ya_registrado_este_mes(db: Session, user_id: str, perfil_id: str, recurrente_id: str,
                           anio: int, mes: int) -> bool:
    """Este fijo ya tiene un movimiento con el mismo mes y año.

    Sirve para no preguntar "es el mismo?" cuando el usuario ya pagó y esta
    pagando el segundo: la pregunta solo tiene sentido la primera vez.
    """
    return bool(db.query(Transaction).filter(
        Transaction.user_id == user_id, Transaction.perfil_id == perfil_id,
        Transaction.recurrente_id == recurrente_id,
        Transaction.fecha >= f"{anio:04d}-{mes:02d}-01",
        Transaction.fecha <= f"{anio:04d}-{mes:02d}-31",
    ).count())


def sugerir_fijos(db: Session, user_id: str, perfil_id: str, meses: int = 3) -> list[dict]:
    """Fijos que la app propone CREAR porque el usuario repite el mismo gasto.

    Es la otra mitad de la autodeteccion: no es que el fijo ya este y haya que
    confirmarlo, sino que se deduce de los movimientos. Un arriendo que se ha
    pagado los ultimos tres meses con el mismo monto es un fijo que el usuario
    todavia no declaro, y la app puede decírselo.
    """
    desde = _hace_meses(meses)
    filas = db.query(Transaction.fecha, Transaction.tipo, Transaction.monto,
                     Transaction.descripcion, Transaction.categoria_id).filter(
        Transaction.user_id == user_id, Transaction.perfil_id == perfil_id,
        Transaction.fecha >= desde,
    ).order_by(Transaction.fecha.desc()).all()

    # Agrupar por (categoria, dia del mes, monto redondeado): tres pagos iguales
    # el mismo dia de tres meses distintos son casi con seguridad un fijo.
    grupos: dict[tuple, list] = {}
    for fecha, tipo, monto, desc, cat in filas:
        clave = (tipo, fecha.day, round(float(monto), -2))
        grupos.setdefault(clave, []).append((fecha, float(monto), desc or "", cat))

    declarados = {r.nombre.lower() for r in db.query(Recurring).filter_by(
        user_id=user_id, perfil_id=perfil_id).all()}

    out = []
    for (tipo, dia, _), items in grupos.items():
        if len(items) < 2:
            continue
        meses_distintos = {f.year * 12 + f.month for f, _, _, _ in items}
        if len(meses_distintos) < 2:
            continue
        montos = [m for _, m, _, _ in items]
        dispersion = (max(montos) - min(montos)) / min(montos) if min(montos) else 0
        if dispersion > TOLERANCIA_MONTO:
            continue
        # El nombre se propone con lo que el usuario mas escribio: el mas corto
        # suele ser el que escribio ("Arriendo" y no "pago arriendo del mes").
        nombre = min((d for _, _, d, _ in items if d.strip()), key=len, default="").strip()
        if not nombre:
            continue
        if _parecido_nombre(nombre, nombre.lower()) and nombre.lower() in declarados:
            continue
        out.append({
            "nombre": nombre[:120], "tipo": tipo, "dia": dia,
            "monto_sugerido": round(sum(montos) / len(montos), 2),
            "frecuencia": "mensual", "veces_visto": len(items),
            "meses": sorted(meses_distintos)[-3:],
            "categoria_id": items[0][3],
        })
    out.sort(key=lambda s: -s["veces_visto"])
    return out[:5]


def _hace_meses(n: int) -> str:
    from datetime import date, timedelta

    hoy = date.today()
    mes = hoy.month - n
    anio = hoy.year
    while mes <= 0:
        mes += 12
        anio -= 1
    return f"{anio:04d}-{mes:02d}-01"