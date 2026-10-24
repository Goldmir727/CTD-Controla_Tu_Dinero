"""Vocabulario y calendario colombiano: modismos, fechas relativas y quincenas.

Por que vive aparte del modelo: la mayor parte de la comprension de "gaste 15 lucas
en un corrientazo" se resuelve con reglas deterministas (barato, instantaneo, sin
gastar tokens). El modelo solo entra cuando las reglas no alcanzan.

Todo es Colombian a proposito: quincenas (15 y 30), prima (junio/diciembre),
"lucas", "corrientazo", y las fechas relativas que dice la gente al hablar.
"""
import re
import unicodedata
from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.vocabulario import Modismo

DIAS_SEMANA = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Multiplicadores de slang. Se aplican al numero que precede a la palabra.
# Montos dichos sin cifras, tal como habla la gente: "un millón y medio",
# "medio millón". El modelo tambien los entendia, pero los reglas necesitan ver
# el monto en el texto para no marcarlo "dudoso" y obligar a reescribirlo a mano.
NUMEROS_TEXTO = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
                 "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}
_RE_MILLON_MEDIO = re.compile(
    r"\b(un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|\d{1,3})"
    r"\s*mill[oó]n(es)?\s*y\s+medio\b")
_RE_MEDIO_MILLON = re.compile(r"\bmedio\s+mill[oó]n(es)?\b")

MULTIPLICADORES = {
    "mil": 1000, "miles": 1000, "lucas": 1000, "luca": 1000,
    "millones": 1_000_000, "millon": 1_000_000, "mill": 1_000_000,
    "k": 1000, "milones": 1_000_000,
}

# Metodos de pago que se detectan por nombre en el texto.
METODOS_TEXTO = {
    "nequi": "Nequi", "daviplata": "Daviplata", "dale": "Dale",
    "pse": "PSE", "nomina": "Nómina", "nómina": "Nómina",
    "efectivo": "Efectivo", "tarjeta": "Tarjeta", "transferencia": "Transferencia",
    "nequi pay": "Nequi", "credivalores": "PSE",
}

# Palabras que delatan un ingreso. "pagué" es gasto, "me pagaron" es ingreso.
PAGAR_INGRESO = ["me pagaron", "me pagaste", "me pagan", "me paga", "me deposited",
                 "me transfirieron", "entrada", "ingreso", "gane", "gané",
                 "me llego", "me llegó", "recibí", "recibi",
                 "me pagaron la quincena", "liquidacion"]
PAGAR_GASTO = ["pague", "pagué", "pago", "gaste", "gasté", "compre", "compré",
               "cancelé", "cancele", "saqué", "saque"]


def normalizar(texto: str) -> str:
    """minusculas, sin tildes y sin signos raros, para comparar modismos.

    OJO: la ñ se vuelve n (NFD separa la tilde y el acento se descarta). Es
    intencional: "pequeño" y "pequeno" deben dar el mismo match, y el diccionario
    se normaliza con la misma funcion.
    """
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return re.sub(r"[^a-z0-9 ]+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def _parse_numero(crudo: str) -> float:
    """Como se escriben los numeros en Colombia.

    La COMA siempre es decimal. El PUNTO depende de cuantos digitos siguen:
      - varios puntos  -> separador de miles: "1.500.000" -> 1500000
      - un punto + 1 o 2 digitos -> decimal: "1.5 millones" -> 1500000
      - un punto + 3 digitos -> miles: "1.500" -> 1500
    Tratar el punto siempre como miles daba 15.000.000 para "1.5 millones".
    """
    s = (crudo or "").strip().replace(" ", "").replace(" ", "")
    if "," in s:
        entero, _, frac = s.partition(",")
        try:
            return float(f"{entero or 0}.{frac or 0}")
        except ValueError:
            return 0.0
    puntos = s.count(".")
    if puntos == 0:
        try:
            return float(s)
        except ValueError:
            return 0.0
    if puntos >= 2:
        try:
            return float(s.replace(".", ""))
        except ValueError:
            return 0.0
    entero, _, frac = s.partition(".")
    if len(frac) in (1, 2):
        try:
            return float(f"{entero or 0}.{frac}")
        except ValueError:
            return 0.0
    try:
        return float(s.replace(".", ""))
    except ValueError:
        return 0.0


# ---------- modismos ----------

_cache: dict | None = None


def cargar_modismos(db: Session) -> dict[str, list[dict]]:
    """termino normalizado -> candidatos, de mayor a menor prioridad. Se cachea:
    la tabla es global y no cambia entre peticiones."""
    global _cache
    if _cache is None:
        out: dict[str, list[dict]] = {}
        for m in db.query(Modismo).order_by(Modismo.prioridad.desc()).all():
            out.setdefault(normalizar(m.termino), []).append(
                {"categoria": m.categoria, "tipo": m.tipo, "prioridad": m.prioridad, "nota": m.nota}
            )
        _cache = out
    return _cache


def invalidar_cache() -> None:
    global _cache
    _cache = None


def buscar_modismos(texto: str, db: Session) -> list[dict]:
    """Modismos presentes en el texto.

    Busca primero los mas largos para que 'recibo de la luz' gane sobre 'luz', y
    exige limites de palabra: sin ellos "gasté" matcheaba el modismo "gas" (Servicios)
    porque es subcadena.
    """
    mods = cargar_modismos(db)
    t = normalizar(texto)
    hallados: list[dict] = []
    for termino in sorted(mods, key=len, reverse=True):
        # \b no sirve con acentos/ñ; se arma el patron sobre el termino ya normalizado
        # (sin tildes) y se buscan espacios/limites reales alrededor.
        patron = r"(?<![a-z0-9])" + re.escape(termino) + r"(?![a-z0-9])"
        if re.search(patron, t):
            for cand in mods[termino]:
                hallados.append({"termino": termino, **cand})
    return hallados


def categoria_por_modismo(texto: str, db: Session) -> tuple[str | None, str | None]:
    """(categoria, tipo) si el texto nombra un modismo del diccionario."""
    hallados = buscar_modismos(texto, db)
    cats = [h for h in hallados if h["categoria"] != "Otros"]
    if not cats:
        return None, None
    mejor = cats[0]
    return mejor["categoria"], mejor["tipo"]


def metodo_por_texto(texto: str) -> str | None:
    t = normalizar(texto)
    for clave, nombre in METODOS_TEXTO.items():
        if clave in t:
            return nombre
    return None


def tipo_por_texto(texto: str) -> str | None:
    """ingreso o gasto segun el verbo. None si no hay senal clara."""
    t = normalizar(texto)
    for frase in PAGAR_INGRESO:
        if frase in t:
            return "ingreso"
    for frase in PAGAR_GASTO:
        if frase in t:
            return "gasto"
    return None


def montos_en_texto(texto: str) -> list[tuple[float, int, int]]:
    """Extrae montos con slang: '18 mil' -> (18000, pos, pos).
    Devuelve lista de (monto, inicio, fin) para poder partir la frase en trozos."""
    t = (texto or "").lower()
    out: list[tuple[float, int, int]] = []
    # Primero los dichos sin cifras: si "un millon y medio" pasara por el patron
    # de abajo no matchearia nada (no hay digito delante de "millon").
    for m in _RE_MILLON_MEDIO.finditer(t):
        base = NUMEROS_TEXTO.get(m.group(1)) or (float(m.group(1)) if m.group(1).isdigit() else 0)
        if base > 0:
            out.append((base * 1_000_000 + 500_000, m.start(), m.end()))
    for m in _RE_MEDIO_MILLON.finditer(t):
        out.append((500_000, m.start(), m.end()))
    # "millones" antes que "mil": en la alternacion el orden importa, aunque \b
    # evita que "mil" coma dentro de "millones".
    patron = re.compile(r"(\d[\d.,]*)\s*(miles|millones|millon|mil|lucas?|k)\b")
    for m in patron.finditer(t):
        base = _parse_numero(m.group(1))
        if base <= 0:
            continue
        out.append((base * MULTIPLICADORES.get(m.group(2), 1000), m.start(), m.end()))
    return out


def frecuencia_por_texto(texto: str) -> str | None:
    """La periodicidad que el texto declara: "cada quincena" -> quincenal.

    None si no hay senal clara. Se exige la palabra completa: que aparezca
    "quincena" pelado no dice que el pago SEA quincenal, "me pagaron la
    quincena" es un sueldo puntual de una vez.
    """
    t = normalizar(texto)
    # "me pagan cada domingo" es semanal aunque no diga "cada semana": el dia
    # de la semana ES la frecuencia. Va antes que el resto porque "cada domingo"
    # no matchea ninguna de las otras reglas.
    if dia_semana_por_texto(t) is not None:
        return "semanal"
    if re.search(r"\bquincenal(es)?\b|cada\s+quincena|cada\s+quince\b|cada\s+1[45]\s+dias?", t):
        return "quincenal"
    if re.search(r"\bsemanal(es)?\b|cada\s+semana|todas?\s+las\s+semanas|cada\s+7\s+dias?", t):
        return "semanal"
    if re.search(r"\bmensual(es)?\b|cada\s+mes\b", t):
        return "mensual"
    return None


def dia_semana_por_texto(texto: str) -> int | None:
    """El dia de la semana de un fijo: "cada domingo" -> 6 (0 = lunes).

    Se exige que el texto diga que se REPITE ("cada", "todos los", "los
    domingos"): "el lunes pagué el arriendo" es un movimiento de un dia, no un
    pago semanal, y marcarlo como fijo semanal inventaria tres pagos mas al mes.
    """
    t = normalizar(texto)
    m = re.search(r"\b(?:cada|todos?\s+los?)\s+"
                  r"(lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)\b", t)
    if not m:
        m = re.search(r"\blos\s+(lunes|martes|miercoles|jueves|viernes|sabados|domingos)\b", t)
    if not m:
        return None
    nombre = m.group(1)
    if nombre not in DIAS_SEMANA and nombre.endswith("s"):
        nombre = nombre[:-1]
    return DIAS_SEMANA.get(nombre)


# ---------- fechas relativas ----------

_RE_DIA_MES = re.compile(r"\b(\d{1,2})\s*(?:de\s*)?([a-z]+)\b")
_RE_DIA = re.compile(r"\b(\d{1,2})\b")
_RE_HACE = re.compile(r"hace\s+(\d+)\s*(d[ií]a|dias|d[ií]as|semana|semanas|mes|meses)")


def resolver_fecha(texto: str, hoy: date | None = None) -> date | None:
    """Interpreta fechas relativas en español colombiano. None si no encuentra
    senal de fecha (el llamador entonces usa hoy)."""
    hoy = hoy or date.today()
    t = normalizar(texto)

    if re.search(r"\bhoy\b", t):
        return hoy
    if re.search(r"\banteayer\b", t):
        return hoy - timedelta(days=2)
    if re.search(r"\bpasado\s+mañana\b|\bpasado\s+manana\b", t):
        # 2 dias al futuro excede el margen de RN-03: no se adivina.
        return None
    if re.search(r"\bmañana\b|\bmanana\b", t):
        return hoy + timedelta(days=1)
    if re.search(r"\bayer\b", t):
        return hoy - timedelta(days=1)
    if re.search(r"\bhace\s+un\s+mes|hace\s+el\s+mes\s+pasado", t):
        return (hoy.replace(day=1) - timedelta(days=1))
    if re.search(r"mes\s+pasado", t):
        return (hoy.replace(day=1) - timedelta(days=1))
    if re.search(r"la\s+semana\s+pasada", t):
        return hoy - timedelta(days=7)

    m = _RE_HACE.search(t)
    if m:
        n = int(m.group(1))
        unidad = m.group(2)
        if unidad.startswith("d"):
            return hoy - timedelta(days=n)
        if unidad.startswith("semana"):
            return hoy - timedelta(weeks=n)
        return hoy - timedelta(days=30 * n)

    # "el viernes", "la ultima vez que fui el martes"
    for nombre, idx in DIAS_SEMANA.items():
        if re.search(rf"\b{nombre}\b", t):
            delta = (hoy.weekday() - idx) % 7
            return hoy - timedelta(days=delta)

    # "el 15 de marzo" o "15 de marzo": aqui la palabra que sigue SI es un mes.
    m = _RE_DIA_MES.search(t)
    if m:
        dia = int(m.group(1))
        mes = MESES.get(m.group(2))
        if mes:
            anio = hoy.year
            cand = date(anio, mes, min(dia, 28))
            if cand > hoy + timedelta(days=1):
                cand = date(anio - 1, mes, min(dia, 28))
            return cand

    # "el 15" pelado. Antes esto aceptaba cualquier palabra como si fuera un mes
    # ("el 15 pagué" -> mes "pague") y de ahi salia una fecha del año pasado.
    # Ahora: solo dia del mes en curso, y si cae muy lejos se devuelve None para
    # que el llamador use hoy o pregunte.
    if re.search(r"\bel\s+\d{1,2}\b|\bdel\s+\d{1,2}\b", t):
        d = _RE_DIA.search(t)
        if d:
            dia = int(d.group(1))
            if 1 <= dia <= dias_del_mes(f"{hoy.year:04d}-{hoy.month:02d}"):
                cand = hoy.replace(day=dia)
                if cand <= hoy + timedelta(days=1):
                    return cand
    return None


# ---------- quincenas ----------

def quincena(fecha: date | None = None) -> dict:
    """La Colombia cobra por quincenas: dias 1-15 y 16-30/31.

    Devuelve el identificador y los limites, para agrupar movimientos y medir
    "como vas en esta quincena".
    """
    f = fecha or date.today()
    if f.day <= 15:
        numero, inicio, fin = 1, date(f.year, f.month, 1), date(f.year, f.month, 15)
    else:
        numero, inicio = 2, date(f.year, f.month, 16)
        # monthrange y no "31 o 30": febrero tiene 28 (29 en bisiesto) y pedir el
        # dia 30 de febrero revienta con ValueError. Eso era un 500 desde el 16
        # hasta el 28 de febrero, todos los años.
        fin = date(f.year, f.month, monthrange(f.year, f.month)[1])
    total = (fin - inicio).days + 1
    transcurridos = (f - inicio).days + 1 if inicio <= f <= fin else total
    restantes = max(total - transcurridos, 0)
    return {"etiqueta": f"{f.year}-{f.month:02d}-Q{numero}",
            "anio": f.year, "mes": f.month, "numero": numero,
            "inicio": inicio.isoformat(), "fin": fin.isoformat(),
            "dias_totales": total, "dias_transcurridos": transcurridos,
            "dias_restantes": restantes,
            "mitad": "primera" if numero == 1 else "segunda"}


def etiqueta_quincena(etiqueta: str) -> str:
    """'2026-10-Q1' -> 'primera quincena de octubre'."""
    try:
        _, m, q = etiqueta.split("-")
        nombres = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                   "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        return f"{'primera' if q == 'Q1' else 'segunda'} quincena de {nombres[int(m) - 1]}"
    except (ValueError, IndexError):
        return etiqueta


def dias_del_mes(mes: str) -> int:
    """'2026-10' -> 31. Un mes de 28 dias no es un mes de 30."""
    try:
        a, m = int(mes[:4]), int(mes[5:7])
        return monthrange(a, m)[1]
    except (ValueError, IndexError):
        return 30