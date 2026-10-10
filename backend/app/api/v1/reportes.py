"""Reportes detallados para los graficos de /analisis.

Los basicos (`/reportes/evolucion` y `/reportes/distribucion`) siguen siendo gratis
en resumen.py. Todo lo de aqui es PRO: es la parte que justifica la suscripcion.

Ningun endpoint recalcula a mano: todos delegan en services/finanzas.py para que
el grafico, el PDF y el chatbot muestren la misma cifra.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.plan import PLANES, require_plan
from app.models.finance import Account, Category, PaymentMethod, Transaction
from app.models.goals import Goal, GoalAporte
from app.models.user import User
from app.services import finanzas as fin
from app.services.calculos import balance_mes

router = APIRouter(tags=["reportes"], dependencies=[Depends(require_plan(
    "reportes_detallados",
    "Los reportes detallados son función PRO. Activa tu plan para verlos.",
))])


def _meses(n: int, hasta: str) -> list[str]:
    """n meses terminando en `hasta`, DEL MAS ANTIGUO AL MAS RECIENTE (para graficos).

    OJO: el orden es inverso al de finanzas._meses_hacia_atras, que devuelve del mas
    reciente al mas antiguo. Por eso aqui se usa [0] para el inicio y [-1] para el fin.
    """
    a, m = int(hasta[:4]), int(hasta[5:7])
    out = []
    for i in range(n - 1, -1, -1):
        y, mm = a, m - i
        while mm < 1:
            mm += 12
            y -= 1
        out.append(f"{y:04d}-{mm:02d}")
    return out


def _mes_anterior(ym: str) -> str:
    """El mes justo antes de `ym`. Ojo: NO es _meses(n)[0], que devuelve el mas reciente."""
    a, m = int(ym[:4]), int(ym[5:7]) - 1
    if m < 1:
        m, a = 12, a - 1
    return f"{a:04d}-{m:02d}"


def _por_categoria(db: Session, user_id: str, tipo: str) -> dict:
    """Una sola consulta: total por categoria."""
    agg = db.query(
        Transaction.categoria_id,
        func.sum(Transaction.monto).label("total"),
        func.count(Transaction.id).label("n"),
    ).filter(Transaction.user_id == user_id, Transaction.tipo == tipo).group_by(
        Transaction.categoria_id).all()
    nombres = {c.id: c.nombre for c in db.query(Category).filter_by(user_id=user_id).all()}
    filas = [{"categoria_id": cid, "nombre": nombres.get(cid, "Sin categoría"),
              "total": float(t or 0), "movimientos": int(n or 0)} for cid, t, n in agg]
    total = sum(f["total"] for f in filas)
    for f in filas:
        f["porcentaje"] = round(f["total"] / total * 100, 2) if total else 0
    return {"items": sorted(filas, key=lambda x: x["total"], reverse=True), "total": round(total, 2)}


@router.get("/reportes/categorias")
def categorias(tipo: str = Query("gasto", pattern="^(gasto|ingreso)$"),
               desde: str | None = None, hasta: str | None = None,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Dona de distribución + tendencia por categoría. Es el gráfico de tu referencia."""
    dist = _por_categoria(db, user.id, tipo)
    nombres = {str(c.id): c.nombre for c in db.query(Category).filter_by(user_id=user.id).all()}
    # Tendencia: cada categoría mes a mes, para la línea bajo la dona.
    hasta_mes = hasta or fin.mes_actual()
    meses = _meses(12, hasta_mes)
    desde_mes = desde or meses[0]
    filas = db.query(
        func.to_char(Transaction.fecha, "YYYY-MM").label("m"),
        Transaction.categoria_id,
        func.sum(Transaction.monto).label("total"),
    ).filter(Transaction.user_id == user.id, Transaction.tipo == tipo,
             func.to_char(Transaction.fecha, "YYYY-MM") >= desde_mes,
             func.to_char(Transaction.fecha, "YYYY-MM") <= hasta_mes,
             ).group_by("m", Transaction.categoria_id).all()

    por_mes: dict[str, dict[str, float]] = {}
    for m, cid, total in filas:
        por_mes.setdefault(str(m), {})[str(cid)] = float(total or 0)

    series = []
    for m in meses:
        if m not in por_mes:
            continue
        puntos = sorted(por_mes[m].items(), key=lambda kv: -kv[1])
        series.append({"mes": m, "puntos": [
            {"categoria_id": cid, "categoria": nombres.get(cid, "Sin categoría"), "total": total}
            for cid, total in puntos]})

    return {"tipo": tipo, "meses": meses, "distribucion": dist["items"], "total": dist["total"],
            "tendencia": series, "top": [f["nombre"] for f in dist["items"][:6]]}


@router.get("/reportes/comparativa")
def comparativa(meses: int = 6, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """Ingresos vs gastos vs balance, mes a mes. Barras agrupadas."""
    meses = max(2, min(meses, 24))
    claves = _meses(meses, fin.mes_actual())
    agg = db.query(
        func.to_char(Transaction.fecha, "YYYY-MM").label("m"),
        func.sum(case((Transaction.tipo == "ingreso", Transaction.monto), else_=0)),
        func.sum(case((Transaction.tipo == "gasto", Transaction.monto), else_=0)),
    ).filter(Transaction.user_id == user.id).group_by("m").all()
    por_mes = {r[0]: (float(r[1] or 0), float(r[2] or 0)) for r in agg}
    items = []
    for k in claves:
        ing, gas = por_mes.get(k, (0.0, 0.0))
        items.append({"mes": k, "ingresos": ing, "gastos": gas, "balance_mes": balance_mes(ing, gas),
                      "tasa_ahorro": round(balance_mes(ing, gas) / ing * 100, 2) if ing else 0})
    return {"items": items, "meses": meses,
            "totales": {"ingresos": round(sum(i["ingresos"] for i in items), 2),
                        "gastos": round(sum(i["gastos"] for i in items), 2),
                        "balance_mes": round(sum(i["balance_mes"] for i in items), 2)}}


@router.get("/reportes/fijos")
def fijos(meses: int = 6, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Apilado: cuanto de cada mes son gastos fijos y cuanto variable."""
    meses = max(2, min(meses, 24))
    claves = _meses(meses, fin.mes_actual())
    f = fin.fijos_mensuales(db, user.id)
    agg = db.query(
        func.to_char(Transaction.fecha, "YYYY-MM").label("m"),
        func.sum(case((Transaction.tipo == "gasto", Transaction.monto), else_=0)),
        func.sum(case((Transaction.tipo == "ingreso", Transaction.monto), else_=0)),
    ).filter(Transaction.user_id == user.id).group_by("m").all()
    por_mes = {r[0]: (float(r[2] or 0), float(r[1] or 0)) for r in agg}
    items = []
    for k in claves:
        ing, gas = por_mes.get(k, (0.0, 0.0))
        var = round(max(gas - f["gastos_fijos_mes"], 0), 2)
        items.append({"mes": k, "ingresos": ing, "fijos": f["gastos_fijos_mes"],
                      "variables": var, "total_gastos": gas,
                      "ratio_fijo": round(f["gastos_fijos_mes"] / gas * 100, 2) if gas else 0})
    return {"items": items, "fijos_mes": f["gastos_fijos_mes"],
            "ingresos_fijos_mes": f["ingresos_fijos_mes"],
            "neto_fijo_mes": f["neto_fijo_mes"], "detalle": f["detalle"],
            "ratio_fijo_promedio": round(sum(i["ratio_fijo"] for i in items) / len(items), 2),
            "estimacion": True}


@router.get("/reportes/metodos")
def metodos(meses: int = 6, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """En que metodo de pago se va el dinero."""
    meses = max(2, min(meses, 24))
    claves = _meses(meses, fin.mes_actual())
    agg = db.query(
        Transaction.metodo_id,
        func.sum(case((Transaction.tipo == "gasto", Transaction.monto), else_=0)),
        func.sum(case((Transaction.tipo == "ingreso", Transaction.monto), else_=0)),
    ).filter(Transaction.user_id == user.id).group_by(Transaction.metodo_id).all()
    nombres = {m.id: m.nombre for m in db.query(PaymentMethod).filter_by(user_id=user.id).all()}
    filas = [{"metodo_id": mid, "nombre": nombres.get(mid, "Sin método"),
              "gastos": float(g or 0), "ingresos": float(i or 0)} for mid, g, i in agg]
    total = sum(f["gastos"] for f in filas)
    for f in filas:
        f["porcentaje"] = round(f["gastos"] / total * 100, 2) if total else 0
    return {"items": sorted(filas, key=lambda x: x["gastos"], reverse=True),
            "total_gastos": round(total, 2), "meses": meses, "periodo": claves}


@router.get("/reportes/calendario")
def calendario(mes: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Mapa de calor dia x categoria, para la vista Calendario."""
    mes = mes or fin.mes_actual()
    y, m = int(mes[:4]), int(mes[5:7])
    ultimo = (date(y + (m == 12), 1 if m == 12 else m + 1, 1) - timedelta(days=1)).day
    # extract('day') devuelve numerico directo; un cast sobre to_char obligaba a
    #agrupar por texto y no se podia sumar.
    dia_col = func.extract("day", Transaction.fecha).label("dia")
    filas = db.query(
        dia_col,
        Transaction.tipo,
        func.sum(Transaction.monto).label("total"),
    ).filter(Transaction.user_id == user.id,
             func.to_char(Transaction.fecha, "YYYY-MM") == mes).group_by(dia_col, Transaction.tipo).all()
    por_dia: dict[int, dict] = {}
    for dia, tipo, total in filas:
        d = por_dia.setdefault(int(dia), {"dia": int(dia), "ingresos": 0.0, "gastos": 0.0})
        # Transaction.tipo es singular ("gasto"); las claves del dict van en plural.
        d["gastos" if tipo == "gasto" else "ingresos"] = float(total or 0)
    dias = []
    for d in range(1, ultimo + 1):
        fila = por_dia.get(d, {"dia": d, "ingresos": 0.0, "gastos": 0.0})
        fila["balance"] = round(fila["ingresos"] - fila["gastos"], 2)
        dias.append(fila)
    metas = [{"id": g.id, "nombre": g.nombre, "objetivo": float(g.objetivo),
              "fecha_objetivo": str(g.fecha_objetivo) if g.fecha_objetivo else None}
             for g in db.query(Goal).filter_by(user_id=user.id).all()]
    aportes = db.query(GoalAporte.goal_id, func.sum(GoalAporte.monto)).filter(
        GoalAporte.user_id == user.id).group_by(GoalAporte.goal_id).all()
    por_meta = {g: float(t or 0) for g, t in aportes}
    return {"mes": mes, "dias": dias, "ultimo_dia": ultimo,
            "dias_con_gasto": sum(1 for d in dias if d["gastos"] > 0),
            "totales": {"ingresos": round(sum(d["ingresos"] for d in dias), 2),
                        "gastos": round(sum(d["gastos"] for d in dias), 2)},
            "metas": [{**mt, "ahorrado": round(por_meta.get(mt["id"], 0.0), 2)} for mt in metas]}


@router.get("/reportes/ranking")
def ranking(dim: str = Query("categoria", pattern="^(categoria|cuenta)$"), meses: int = 3,
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Top N con delta contra el periodo anterior: "esto subio 40%"."""
    meses = max(1, min(meses, 12))
    claves = _meses(meses, fin.mes_actual())
    rango, rango_fin = claves[0], claves[-1]  # [0] antiguo, [-1] reciente
    # Periodo anterior de IGUAL longitud, para que el delta sea comparable: si no,
    # comparar 2 meses contra 1 inventa crecimientos que no existen.
    previos = _meses(meses, _mes_anterior(rango))
    rango_previo, rango_previo_fin = previos[0], previos[-1]

    if dim == "categoria":
        campo = Transaction.categoria_id
        nombres = {str(c.id): c.nombre for c in db.query(Category).filter_by(user_id=user.id).all()}
    else:
        campo = Transaction.cuenta_id
        nombres = {str(a.id): a.nombre for a in db.query(Account).filter_by(user_id=user.id).all()}

    def _agg(desde: str, hasta: str) -> dict:
        filas = db.query(campo, func.sum(Transaction.monto)).filter(
            Transaction.user_id == user.id, Transaction.tipo == "gasto",
            func.to_char(Transaction.fecha, "YYYY-MM") >= desde,
            func.to_char(Transaction.fecha, "YYYY-MM") <= hasta,
        ).group_by(campo).all()
        return {str(k): float(v or 0) for k, v in filas}

    ahora, antes = _agg(rango, rango_fin), _agg(rango_previo, rango_previo_fin)
    claves_id = set(ahora) | set(antes)
    items = []
    for k in claves_id:
        a, b = ahora.get(k, 0.0), antes.get(k, 0.0)
        items.append({"id": k, "nombre": nombres.get(k, "Sin asignar"),
                      "actual": a, "anterior": b,
                      "delta": round(a - b, 2),
                      "delta_porcentaje": round((a - b) / b * 100, 1) if b else None})
    items.sort(key=lambda x: x["actual"], reverse=True)
    total = sum(i["actual"] for i in items) or 1
    for i in items:
        i["porcentaje"] = round(i["actual"] / total * 100, 2)
    return {"dim": dim, "meses": meses,
            "periodo": {"desde": rango, "hasta": rango_fin},
            "periodo_anterior": {"desde": rango_previo, "hasta": rango_previo_fin},
            "items": items[:10], "total": round(total, 2)}
