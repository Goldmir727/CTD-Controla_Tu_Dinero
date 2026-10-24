"""Revision quincenal: como vas en esta quincena y que se viene encima.

Por que la quincena y no el mes: en Colombia casi nadie cobra por mes. La quincena
(1-15 y 16-30) es la unidad real de la vida financiera, y es cuando seaude "me
alcanza o no me alcanza". Preguntar por el mes entero llega tarde.

Que responde:
- Cuanto gastaste en la quincena y cuanto te queda.
- Que gastos fijos caen en esta quincena (el arriendo del dia 5 es de la primera,
  el del dia 20 es de la segunda).
- Si hoy vas a terminar la quincena con plata o en rojo.
- Que presupuestos van mas rapido que el calendario: ese es el aviso que evita el
  "ya gastaste el 80% de ocio y apenas vamos el dia 12".

Todo se apoya en services/finanzas.py: la app no puede mostrar dos versiones de
la misma cifra. Y todo lo predictivo va marcado como estimacion (RN-07).
"""
from datetime import date

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.finance import Budget, Category, Transaction
from app.models.goals import Recurring
from app.services import colombia as co
from app.services import finanzas as fin
from app.services import periodo as per
from app.services import recurrencia as recu
# Los mensajes van al chat y al PDF: si usan el formato ingles ("1,301,667") el
# usuario lee otra cifra que la de la tabla de al lado ("$1.301.667").
from app.services.formato import dinero

# Umbral para quejarse: si vas 20 puntos por encima de lo que marca el calendario.
DELTA_ALERTA = 20


def _ocurrencias_de_un_fijo(r, desde: date, hasta: date) -> list[date]:
    """Las fechas reales en que cae un fijo entre dos fechas.

    El conteo por dia del mes se equivocaba en dos casos que el usuario nota: un
    semanal anclado al 18 solo aparecia el 18 y el 25 (dos veces), y un
    quincenal con dia > 15 perdia la segunda ocurrencia porque el 35 no existe.
    El calendario lo resuelve services/recurrencia.
    """
    return recu.ocurrencias(desde, hasta, r.frecuencia, r.dia, r.dia_semana)


def fijos_del_periodo(db: Session, user_id: str, perfil_id: str, q: dict) -> dict:
    """Cuanto fijo vence en este periodo, y el detalle de que es.

    Sirve igual para mes y para quincena: se lee el rango real del periodo, asi
    que un arriendo el dia 20 cuenta en el mes (una vez) y en la segunda quincena
    (una vez), no se inventa el "si es mensual, una vez".
    """
    desde = date.fromisoformat(q["inicio"])
    hasta = date.fromisoformat(q["fin"])
    filas = db.query(Recurring).filter_by(user_id=user_id, perfil_id=perfil_id, activo=True).all()
    detalle, total = [], 0.0
    for r in filas:
        fechas = _ocurrencias_de_un_fijo(r, desde, hasta)
        veces = len(fechas)
        if veces <= 0:
            continue
        monto = round(float(r.monto) * veces, 2)
        total = round(total + monto, 2)
        detalle.append({"nombre": r.nombre, "tipo": r.tipo, "monto": monto,
                         "dia": r.dia, "dia_semana": r.dia_semana, "veces": veces,
                         "frecuencia": r.frecuencia,
                         "etiqueta": recu.etiqueta(r.frecuencia, r.dia, r.dia_semana),
                         "proxima": fechas[0].isoformat()})
    detalle.sort(key=lambda x: -x["monto"])
    return {"total": total, "items": detalle,
            "ingresos": round(sum(x["monto"] for x in detalle if x["tipo"] == "ingreso"), 2),
            "gastos": round(sum(x["monto"] for x in detalle if x["tipo"] == "gasto"), 2)}


# Alias para los llamadores viejos.
fijos_de_la_quincena = fijos_del_periodo


def gastado_periodo(db: Session, user_id: str, perfil_id: str, desde: str, hasta: str) -> dict:
    fila = db.query(
        func.sum(case((Transaction.tipo == "ingreso", Transaction.monto), else_=0)),
        func.sum(case((Transaction.tipo == "gasto", Transaction.monto), else_=0)),
        func.count(Transaction.id),
    ).filter(Transaction.user_id == user_id, Transaction.perfil_id == perfil_id,
             Transaction.fecha >= desde, Transaction.fecha <= hasta).first()
    ing, gas, n = (float(fila[0] or 0), float(fila[1] or 0), int(fila[2] or 0)) if fila else (0.0, 0.0, 0)
    return {"ingresos": round(ing, 2), "gastos": round(gas, 2),
            "balance": round(ing - gas, 2), "movimientos": n}


# Alias para los llamadores viejos.
gastado_quincena = gastado_periodo


def revision(db: Session, user_id: str, perfil_id: str, fecha: date | None = None,
             usa_quincena: bool = True) -> dict:
    """Estado del periodo en curso + proyeccion a su cierre.

    ``usa_quincena`` decide el corte: False = mes completo (dia 1 al ultimo),
    True = quincena. El default True es solo para no romper los llamadores
    antiguos; la API siempre pasa el valor del usuario.
    """
    hoy = fecha or date.today()
    q = per.periodo(hoy, usa_quincena)
    desde, hasta = q["inicio"], q["fin"]

    movs = gastado_periodo(db, user_id, perfil_id, desde, hasta)
    fijos = fijos_del_periodo(db, user_id, perfil_id, q)
    disp = fin.disponible(db, user_id, perfil_id)

    # Proyeccion: lo que ya gasto + lo que falta por gastar a ritmo normal.
    transcurridos, total_dias = q["dias_transcurridos"], q["dias_totales"]
    fraccion = transcurridos / total_dias if total_dias else 0
    variables = fin.promedio_variables(db, user_id, perfil_id, hoy.strftime("%Y-%m"))

    fijos_esperados = round(fijos["total"] * (1 - fraccion), 2)
    variables_esperados = round(variables["promedio_variables"] * (1 - fraccion), 2)
    cierre_estimado = round(disp["total"] + movs["balance"] - fijos_esperados - variables_esperados, 2)

    # Comparacion con el mismo periodo del mes anterior.
    anterior_q = per.periodo_anterior(q, usa_quincena)
    anterior = _comparar(db, user_id, perfil_id, anterior_q, usa_quincena)

    alertas = alertas_presupuesto(db, user_id, perfil_id, hoy)

    # Cuanto queda libre para la meta, sin prometer nada.
    libre = round(disp["total"] - fijos["gastos"], 2)

    return {
        "quincena": q,
        "usa_quincena": usa_quincena,
        "etiqueta_legible": per.etiqueta_periodo(q["etiqueta"], usa_quincena),
        "hoy": hoy.isoformat(),
        "movimientos": movs,
        "fijos": fijos,
        "disponible": disp["total"],
        "libre_para_metas": max(libre, 0.0),
        "proyeccion": {
            "saldo_al_cerrar": cierre_estimado,
            "fijo_por_pagar": fijos_esperados,
            "variable_esperada": variables_esperados,
            "estimacion": True,
            "nota": "Proyecta lo fijo y tu promedio de variables hasta el cierre. "
                    "No anticipa ingresos ni gastos extraordinarios.",
        },
        "comparacion": anterior,
        "alertas": alertas,
        "mensaje": _mensaje(q, movs, cierre_estimado, alertas, libre, usa_quincena),
    }


def _quincena_anterior(q: dict) -> dict | None:
    """Compat: la misma quincena del mes anterior. Ahora vive en services/periodo."""
    return per.periodo_anterior(q, usa_quincena=True)


def _comparar(db: Session, user_id: str, perfil_id: str,
              etiqueta_anterior: dict | None, usa_quincena: bool = True) -> dict | None:
    if not etiqueta_anterior:
        return None
    previo = gastado_periodo(db, user_id, perfil_id, etiqueta_anterior["inicio"],
                              etiqueta_anterior["fin"])
    return {"etiqueta": etiqueta_anterior["etiqueta"],
            "legible": per.etiqueta_periodo(etiqueta_anterior["etiqueta"], usa_quincena),
            "gastos": previo["gastos"], "ingresos": previo["ingresos"],
            "balance": previo["balance"]}


def alertas_presupuesto(db: Session, user_id: str, perfil_id: str, hoy: date | None = None) -> list[dict]:
    """Presupuestos que van mas rapido (o mas lento) que el calendario.

    El aviso que sirve: "Ya gastaste el 80% de Ocio y apenas vamos el dia 12".
    Comparar solo porcentaje gastado no dice nada; hay que contrastarlo con los
    dias que llevan.
    """
    hoy = hoy or date.today()
    mes = hoy.strftime("%Y-%m")
    ultimo = co.dias_del_mes(mes)
    transcurridos = min(hoy.day, ultimo)
    fraccion = transcurridos / ultimo

    presupuestos = db.query(Budget).filter_by(user_id=user_id, perfil_id=perfil_id,
                                            periodo=mes).all()
    alertas = []
    for b in presupuestos:
        gastado = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
            Transaction.user_id == user_id, Transaction.perfil_id == perfil_id,
            Transaction.tipo == "gasto", Transaction.categoria_id == b.categoria_id,
            func.to_char(Transaction.fecha, "YYYY-MM") == mes).scalar() or 0)
        limite = float(b.monto)
        if limite <= 0 or gastado <= 0:
            continue
        pct_gastado = gastado / limite * 100
        if pct_gastado < 80:
            continue
        delta = pct_gastado - fraccion * 100
        ritmo_d = gastado / transcurridos if transcurridos else 0
        estado = "excedido" if pct_gastado > 100 else "muy_rapido"
        cat = db.get(Category, b.categoria_id)
        alertas.append({
            "categoria": cat.nombre if cat else "?",
            "categoria_id": b.categoria_id,
            "presupuestado": limite,
            "gastado": round(gastado, 2),
            "porcentaje": round(pct_gastado, 1),
            "dias_transcurridos": transcurridos,
            "dias_periodo": ultimo,
            "porcentaje_esperado": round(fraccion * 100, 1),
            "delta_puntos": round(delta, 1),
            "ritmo_diario": round(ritmo_d, 2),
            "ritmo_sostenible": round(limite / ultimo, 2),
            "estado": estado,
            "mensaje": _mensaje_presupuesto(cat.nombre if cat else "esa categoría",
                                           round(pct_gastado, 0), transcurridos, ultimo,
                                           ritmo_d, limite / ultimo, delta, pct_gastado > 100),
        })
    alertas.sort(key=lambda a: -a["delta_puntos"])
    return alertas


def _mensaje_presupuesto(nombre: str, pct: float, dia: int, ultimo: int,
                         ritmo_d: float, sostenible: float, delta: float,
                         excedido: bool) -> str:
    faltantes = ultimo - dia
    if excedido:
        return (f"Llevas {pct}% de {nombre} y apenas vas el día {dia} de {ultimo}. "
                f"Te pasaste por {pct - 100:.0f} puntos; este mes no te alcanza sin bajar gastos.")
    if delta >= DELTA_ALERTA:
        return (f"Ya gastaste el {pct:.0f}% de {nombre} y apenas vamos el día {dia} de {ultimo}. "
                f"Vas {delta:.0f} puntos por encima del ritmo; a {dinero(ritmo_d)} "
                f"no alcanzas, el sostenible sería {dinero(sostenible)}. "
                + (f"Ajusta lo de los últimos {faltantes} días." if faltantes > 0
                   else "Ya no queda mes para corregirlo."))
    return (f"Llevas el {pct:.0f}% de {nombre} y vas el día {dia} de {ultimo}: "
            f"un poco más rápido de lo normal.")


def _mensaje(q: dict, movs: dict, cierre: float, alertas: list, libre: float,
             usa_quincena: bool = True) -> str:
    # En quincena el texto necesita articulo ("Vas con la primera quincena"); en
    # mes la etiqueta completa ("octubre de 2026") suena a tema dentro de la
    # frase, asi que adentro se usa "este mes" y la etiqueta queda para el
    # encabezado de la tarjeta.
    if usa_quincena:
        etiqueta = co.etiqueta_quincena(q["etiqueta"])
        vacio = "Todavía no has registrado nada en esta quincena."
        bien = f"Vas con la {etiqueta} y, a este ritmo, cerrarías con {dinero(cierre)}."
        mal = f"Ojo: a este ritmo la {etiqueta} cerraría en {dinero(cierre)}."
    else:
        vacio = "Todavía no has registrado nada este mes."
        bien = f"Este mes vas bien: a este ritmo cerrarías con {dinero(cierre)}."
        mal = f"Ojo: a este ritmo, este mes cerrarías en {dinero(cierre)}."
    partes = []
    if movs["gastos"] == 0 and movs["ingresos"] == 0:
        partes.append(vacio)
    elif cierre >= 0:
        partes.append(bien)
    else:
        partes.append(mal)
    if alertas:
        partes.append(f"Tienes {len(alertas)} "
                      + ("presupuesto" if len(alertas) == 1 else "presupuestos")
                      + " yendo más rápido que el calendario.")
    if libre > 0:
        partes.append(f"Después de los fijos te quedan {dinero(libre)} para tus metas.")
    return " ".join(partes)