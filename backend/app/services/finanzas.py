"""Motor de calculo financiero: la unica fuente de verdad de las simulaciones.

Por que existe: el asesor IA, los endpoints /simulador, /pronostico, /escenarios y
los informes PDF necesitan las MISMAS cifras. Si cada uno calcula por su cuenta,
el chatbot termina contradiciendo a la pantalla. Estas funciones son puras y
deterministas: el modelo las invoca por function calling en vez de inventarlas.

Reglas de negocio que respeta (docs/mvp-alcance.md):
- RN-07: todo resultado predictivo se etiqueta `estimacion`.
- RC-01: los aportes a metas NO mueven saldos, solo seguimiento.
- Los gastos fijos declarados alimentan la proyeccion; los variables se estiman
  con el promedio historico de los meses que ya tienen datos.
"""
from datetime import date, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.finance import Account, Budget, Category, Transaction
from app.models.goals import Goal, GoalAporte, Recurring
from app.services.calculos import (
    balance_mes,
    meta_faltante,
    meta_porcentaje,
    meses_restantes,
    presupuesto_porcentaje,
    saldo_actual,
    tasa_ahorro,
)

VENTANA_PROMEDIO = 3      # meses hacia atras para promediar variables
MIN_MESES_DATOS = 2       # con menos, la proyeccion se marca como muy insegura
FACTOR_FRECUENCIA = {"mensual": 1.0, "quincenal": 2.0, "semanal": 4.33}


# ---------- lecturas agregadas ----------

def _sumas(db: Session, user_id: str, mes: str, tipo: str, cuenta_id: str | None = None) -> float:
    q = db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
        Transaction.user_id == user_id, Transaction.tipo == tipo,
        func.to_char(Transaction.fecha, "YYYY-MM") == mes)
    if cuenta_id:
        q = q.filter(Transaction.cuenta_id == cuenta_id)
    return float(q.scalar() or 0)


def total_mes(db: Session, user_id: str, mes: str) -> dict:
    ing, gas = _sumas(db, user_id, mes, "ingreso"), _sumas(db, user_id, mes, "gasto")
    bal = balance_mes(ing, gas)
    return {"mes": mes, "ingresos": ing, "gastos": gas, "balance_mes": bal,
            "tasa_ahorro": tasa_ahorro(ing, bal)}


def _saldos_cuentas(db: Session, user_id: str) -> tuple[list[dict], float]:
    """RC-01 en una sola pasada: una consulta agrupada en vez de 2 SUMs por cuenta."""
    agg = db.query(
        Transaction.cuenta_id,
        func.sum(case((Transaction.tipo == "ingreso", Transaction.monto),
                      else_=-Transaction.monto)).label("neto"),
    ).filter(Transaction.user_id == user_id).group_by(Transaction.cuenta_id).all()
    por_cuenta = {cid: float(n or 0) for cid, n in agg}
    cuentas, total = [], 0.0
    for c in db.query(Account).filter_by(user_id=user_id).all():
        sal = round(float(c.saldo_inicial) + por_cuenta.get(c.id, 0.0), 2)
        cuentas.append({"id": c.id, "nombre": c.nombre, "tipo": c.tipo, "saldo_actual": sal})
        total += sal
    return cuentas, round(total, 2)


def disponible(db: Session, user_id: str) -> dict:
    cuentas, total = _saldos_cuentas(db, user_id)
    return {"cuentas": cuentas, "total": total}


def _meses_hacia_atras(mes: str, n: int) -> list[str]:
    a, m = int(mes[:4]), int(mes[5:7])
    out = []
    for i in range(n):
        y, mm = a, m - i
        while mm < 1:
            mm += 12
            y -= 1
        out.append(f"{y:04d}-{mm:02d}")
    return out


def _mes_siguiente(mes: str) -> str:
    a, m = int(mes[:4]), int(mes[5:7]) + 1
    if m > 12:
        m, a = 1, a + 1
    return f"{a:04d}-{m:02d}"


def mes_actual() -> str:
    return date.today().strftime("%Y-%m")


# ---------- fijos ----------

def fijos_mensuales(db: Session, user_id: str, solo_activos: bool = True) -> dict:
    """Normaliza los recurrentes a un monto por mes.

    semanal x4.33 y quincenal x2 aproximan el gasto mensual; se marca como
    estimacion porque los meses no tienen semanas exactas.
    """
    q = db.query(Recurring).filter_by(user_id=user_id)
    if solo_activos:
        q = q.filter_by(activo=True)
    ing = gas = 0.0
    detalle = []
    for r in q.all():
        m = round(float(r.monto) * FACTOR_FRECUENCIA[r.frecuencia], 2)
        if r.tipo == "ingreso":
            ing += m
        else:
            gas += m
        detalle.append({"id": r.id, "nombre": r.nombre, "tipo": r.tipo, "monto_mes": m,
                        "frecuencia": r.frecuencia, "dia": r.dia, "activo": r.activo,
                        "confirmado": r.confirmado, "nota": r.nota})
    ing, gas = round(ing, 2), round(gas, 2)
    return {"ingresos_fijos_mes": ing, "gastos_fijos_mes": gas,
            "neto_fijo_mes": round(ing - gas, 2),
            "cantidad": len(detalle),
            "detalle": sorted(detalle, key=lambda x: (x["tipo"], x["nombre"]))}


def promedio_variables(db: Session, user_id: str, hasta_mes: str) -> dict:
    """Promedio mensual de gastos NO fijos, para separar fijos de variables."""
    fijos_gasto = fijos_mensuales(db, user_id)["gastos_fijos_mes"]
    filas = []
    for mes in _meses_hacia_atras(hasta_mes, VENTANA_PROMEDIO):
        t = total_mes(db, user_id, mes)
        if t["gastos"] > 0:
            filas.append({**t, "variables": round(max(t["gastos"] - fijos_gasto, 0), 2)})
    promedio = (round(sum(f["variables"] for f in filas) / len(filas), 2) if filas else 0.0)
    return {"promedio_variables": promedio, "meses_con_datos": len(filas),
            "ventana": VENTANA_PROMEDIO, "detalle": filas,
            "es_estimacion": len(filas) < MIN_MESES_DATOS}


def ratio_fijo(db: Session, user_id: str, mes: str) -> dict:
    """Que porcentaje de los gastos del mes es fijo (compromiso) vs variable."""
    fijos_gasto = fijos_mensuales(db, user_id)["gastos_fijos_mes"]
    t = total_mes(db, user_id, mes)
    if t["gastos"] <= 0:
        return {"mes": mes, "ratio_fijo": 0.0, "gastos_fijos": fijos_gasto,
                "gastos_variables": 0.0, "es_estimacion": True}
    ratio = round(min(fijos_gasto / t["gastos"] * 100, 100), 2)
    return {"mes": mes, "ratio_fijo": ratio, "gastos_fijos": fijos_gasto,
            "gastos_variables": round(max(t["gastos"] - fijos_gasto, 0), 2),
            "es_estimacion": False}


# ---------- simulaciones ----------

def puedo_gastar(db: Session, user_id: str, monto: float, mes: str,
                 categoria: str | None = None) -> dict:
    """La pregunta clasica: si gasto esto mas, me alcanza?"""
    t = total_mes(db, user_id, mes)
    disp = disponible(db, user_id)["total"]
    saldo_despues = round(disp - monto, 2)
    balance_despues = round(t["balance_mes"] - monto, 2)
    res = {"mes": mes, "monto": round(monto, 2), "categoria": categoria,
           "disponible_actual": disp, "ingresos_mes": t["ingresos"],
           "gastos_mes": t["gastos"], "balance_mes": t["balance_mes"],
           "saldo_despues": saldo_despues, "balance_despues": balance_despues,
           "puede": saldo_despues >= 0 and balance_despues >= 0,
           "es_estimacion": True}
    if saldo_despues < 0:
        res["motivo"] = f"Te quedarías en {saldo_despues} si gastas eso hoy."
    elif balance_despues < 0:
        res["motivo"] = ("Tu saldo aguanta, pero el mes cerraria en negativo: "
                         f"ingresas {t['ingresos']} y quedaria en {balance_despues}.")
    else:
        res["motivo"] = (f"Te alcanza: quedarias con {saldo_despues} y el mes cerraria "
                         f"en {balance_despues}.")
    if categoria:
        res["presupuesto"] = _presupuesto_de(db, user_id, mes, categoria)
    return res


def _presupuesto_de(db: Session, user_id: str, mes: str, nombre_categoria: str) -> dict | None:
    cat = db.query(Category).filter_by(user_id=user_id, nombre=nombre_categoria).first()
    if not cat:
        return None
    b = db.query(Budget).filter_by(user_id=user_id, categoria_id=cat.id, periodo=mes).first()
    gastado = float(
        db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
            Transaction.user_id == user_id, Transaction.tipo == "gasto",
            Transaction.categoria_id == cat.id,
            func.to_char(Transaction.fecha, "YYYY-MM") == mes).scalar() or 0)
    if not b:
        return {"categoria": nombre_categoria, "tiene_presupuesto": False, "gastado": gastado,
                "porcentaje": None, "estado": "sin_presupuesto"}
    pct = presupuesto_porcentaje(float(b.monto), gastado)
    return {"categoria": nombre_categoria, "tiene_presupuesto": True,
            "presupuestado": float(b.monto), "gastado": gastado,
            "restante": round(float(b.monto) - gastado, 2), "porcentaje": pct,
            "estado": "excedido" if pct > 100 else ("alerta" if pct >= 80 else "ok")}


def proyeccion(db: Session, user_id: str, desde_mes: str | None = None,
               meses: int = 6) -> dict:
    """Balance esperado mes a mes: fijos declarados + promedio de variables.

    No reinicia el disponible a cero: arrastra el saldo actual mes a mes.
    """
    desde_mes = desde_mes or mes_actual()
    meses = max(1, min(meses, 24))
    fijos = fijos_mensuales(db, user_id)
    variables = promedio_variables(db, user_id, desde_mes)
    saldo = disponible(db, user_id)["total"]
    saldo_ini = saldo
    filas = []
    mes = desde_mes
    for _ in range(meses):
        mes = _mes_siguiente(mes)
        esperado_ing = fijos["ingresos_fijos_mes"]
        esperado_gas = round(fijos["gastos_fijos_mes"] + variables["promedio_variables"], 2)
        esperado_bal = balance_mes(esperado_ing, esperado_gas)
        saldo = round(saldo + esperado_bal, 2)
        filas.append({"mes": mes, "ingresos_esperados": esperado_ing,
                      "gastos_esperados": esperado_gas, "balance_esperado": esperado_bal,
                      "saldo_proyectado": saldo})
    neto = round(fijos["neto_fijo_mes"] + variables["promedio_variables"], 2)
    return {"mes_inicio": desde_mes, "meses": meses, "saldo_inicial": saldo_ini,
            "saldo_final": filas[-1]["saldo_proyectado"] if filas else saldo_ini,
            "neto_mensual_estimado": neto,
            "promedio_variables": variables["promedio_variables"],
            "gastos_fijos_mes": fijos["gastos_fijos_mes"],
            "ingresos_fijos_mes": fijos["ingresos_fijos_mes"],
            "meses_con_datos": variables["meses_con_datos"],
            "items": filas, "estimacion": True,
            "aviso": ("Estimación: proyecta tus fijos declarados y el promedio de tus gastos "
                      "variables. No anticipa ingresos ni gastos extraordinarios.")}


def ruta_meta(db: Session, user_id: str, meta_id: str, aporte_mensual: float,
              hoy: date | None = None) -> dict:
    """En cuantos meses cumples una meta con un aporte mensual, partiendo de lo ahorrado."""
    hoy = hoy or date.today()
    meta = db.query(Goal).filter_by(id=meta_id, user_id=user_id).first()
    if not meta:
        return {"error": "Meta no encontrada"}
    ahorrado = float(db.query(func.coalesce(func.sum(GoalAporte.monto), 0))
                     .filter_by(goal_id=meta.id).scalar() or 0)
    faltante = meta_faltante(float(meta.objetivo), ahorrado)
    r = ruta_meta_desde_faltante(faltante, aporte_mensual, meta.fecha_objetivo, hoy)
    r["meta"] = meta.nombre
    r["objetivo"] = float(meta.objetivo)
    r["ahorrado"] = ahorrado
    return r


def ruta_meta_desde_faltante(faltante: float, aporte_mensual: float,
                             fecha_objetivo: date | None = None,
                             hoy: date | None = None) -> dict:
    """Ruta de ahorro a partir del faltante real y un aporte mensual."""
    hoy = hoy or date.today()
    faltante = max(float(faltante), 0.0)
    base = {"faltante": round(faltante, 2), "aporte_mensual": round(float(aporte_mensual), 2),
            "estimacion": True}
    if aporte_mensual <= 0:
        return {**base, "meses": None, "alcanzable": False, "requerido_mensual": None,
                "razon": ("Con aporte 0 el faltante nunca baja. "
                          "Dime cuanto podrias ahorrar al mes y lo calculo.")}
    meses = int(-(-faltante // aporte_mensual))  # division entera, redondeo hacia arriba
    res = {**base, "meses": meses, "alcanzable": True,
           "fecha_aproximada": (hoy + timedelta(days=meses * 30)).isoformat()}
    limite = meses_restantes(fecha_objetivo, hoy) if fecha_objetivo else None
    if limite is not None:
        res["meses_hasta_fecha"] = limite
        res["alcanza_en_fecha"] = meses <= limite
        if not res["alcanza_en_fecha"]:
            req = round(faltante / limite, 2)
            res["requerido_mensual"] = req
            res["razon"] = (f"Aportando {aporte_mensual:.0f} al mes tardas {meses} meses y "
                            f"te quedan {limite} hasta la fecha de la meta. "
                            f"Necesitas cerca de {req:.0f} al mes para llegar a tiempo.")
    return res


def meta_mas_alcanzable(db: Session, user_id: str, hoy: date | None = None) -> dict | None:
    """Cual meta priorizar: la que necesita menos esfuerzo para un salto de progreso."""
    hoy = hoy or date.today()
    mejor = None
    for g in db.query(Goal).filter_by(user_id=user_id).all():
        ah = float(db.query(func.coalesce(func.sum(GoalAporte.monto), 0))
                   .filter_by(goal_id=g.id).scalar() or 0)
        f = meta_faltante(float(g.objetivo), ah)
        if f <= 0:
            continue
        mr = meses_restantes(g.fecha_objetivo, hoy)
        req = round(f / mr, 2) if mr else None
        cand = {"meta": g.nombre, "faltante": f, "meses_restantes": mr,
                "requerido_mensual": req, "porcentaje": meta_porcentaje(float(g.objetivo), ah)}
        if mejor is None or (cand["requerido_mensual"] or 9e18) < (mejor["requerido_mensual"] or 9e18):
            mejor = cand
    return mejor
