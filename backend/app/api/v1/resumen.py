from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.models.perfil import Perfil
from app.models.finance import Account, Category, Transaction
from app.models.goals import Goal
from app.models.user import User
from app.services import finanzas as fin
from app.services.calculos import balance_mes, saldo_actual, tasa_ahorro

router = APIRouter(tags=["resumen"])


@router.get("/resumen")
def resumen(mes: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    ing = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
        Transaction.user_id == user.id, Transaction.perfil_id == perfil.id, Transaction.tipo == "ingreso",
        func.to_char(Transaction.fecha, "YYYY-MM") == mes).scalar() or 0)
    gas = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
        Transaction.user_id == user.id, Transaction.perfil_id == perfil.id, Transaction.tipo == "gasto",
        func.to_char(Transaction.fecha, "YYYY-MM") == mes).scalar() or 0)
    bal = balance_mes(ing, gas)
    por_cuenta = []
    for a in db.query(Account).filter_by(user_id=user.id, perfil_id=perfil.id).all():
        ai = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
            Transaction.cuenta_id == a.id, Transaction.tipo == "ingreso",
            func.to_char(Transaction.fecha, "YYYY-MM") == mes).scalar() or 0)
        ag = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
            Transaction.cuenta_id == a.id, Transaction.tipo == "gasto",
            func.to_char(Transaction.fecha, "YYYY-MM") == mes).scalar() or 0)
        gi = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter_by(cuenta_id=a.id, tipo="ingreso").scalar() or 0)
        gg = float(db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter_by(cuenta_id=a.id, tipo="gasto").scalar() or 0)
        por_cuenta.append({"cuenta_id": a.id, "nombre": a.nombre, "ingresos": ai, "gastos": ag,
                           "saldo_actual": saldo_actual(float(a.saldo_inicial), gi, gg)})
    return {"mes": mes, "ingresos": ing, "gastos": gas, "balance_mes": bal,
            "ahorro": bal, "tasa_ahorro": tasa_ahorro(ing, bal), "por_cuenta": por_cuenta,
            "mensaje": f"Gastaste {gas} de {ing}. Balance {bal}."}


@router.get("/reportes/evolucion")
def evolucion(meses: int = 6, hasta: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    from datetime import date as _date

    meses = max(1, min(meses, 12))
    if hasta:
        try:
            y, m = map(int, hasta.split("-"))
        except Exception:
            raise HTTPException(422, "hasta debe ser YYYY-MM")
    else:
        hoy = _date.today()
        y, m = hoy.year, hoy.month
    nombres = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
               "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    # Una sola consulta agrupada en vez de 2 SUMs por mes (era N+1).
    agg = db.query(
        func.to_char(Transaction.fecha, "YYYY-MM").label("m"),
        func.coalesce(func.sum(case((Transaction.tipo == "ingreso", Transaction.monto), else_=0)), 0),
        func.coalesce(func.sum(case((Transaction.tipo == "gasto", Transaction.monto), else_=0)), 0),
    ).filter(Transaction.user_id == user.id, Transaction.perfil_id == perfil.id).group_by("m").all()
    por_mes = {r[0]: (float(r[1] or 0), float(r[2] or 0)) for r in agg}
    items = []
    for i in range(meses - 1, -1, -1):
        yy, mm = y, m - i
        while mm <= 0:
            mm += 12
            yy -= 1
        key = f"{yy:04d}-{mm:02d}"
        ing, gas = por_mes.get(key, (0.0, 0.0))
        items.append({"mes": key, "ingresos": ing, "gastos": gas, "balance_mes": balance_mes(ing, gas)})
    if len(items) >= 2 and items[-2]["ingresos"] > 0:
        pct = round((items[-1]["ingresos"] - items[-2]["ingresos"]) / items[-2]["ingresos"] * 100)
        ult, prev = items[-1]["mes"], items[-2]["mes"]
        un, pn = nombres[int(ult.split("-")[1])], nombres[int(prev.split("-")[1])]
        palabra = "más" if pct >= 0 else "menos"
        mensaje = f"En {un} ingresaste {abs(pct)}% {palabra} que en {pn}."
    elif len(items) >= 2:
        un = nombres[int(items[-1]["mes"].split("-")[1])]
        mensaje = f"En {un} no hubo ingresos el mes anterior para comparar."
    else:
        mensaje = "Sin datos suficientes."
    return {"items": items, "mensaje": mensaje}


@router.get("/reportes/distribucion")
def distribucion(desde: str | None = None, hasta: str | None = None, tipo: str = "gasto",
                 db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    q = db.query(Transaction.categoria_id, func.coalesce(func.sum(Transaction.monto), 0)).filter(
        Transaction.user_id == user.id, Transaction.perfil_id == perfil.id, Transaction.tipo == tipo)
    if desde:
        q = q.filter(Transaction.fecha >= desde)
    if hasta:
        q = q.filter(Transaction.fecha <= hasta)
    rows = q.group_by(Transaction.categoria_id).all()
    total = sum(float(t) for _, t in rows) or 0
    out = []
    for cat_id, s in rows:
        cat = db.get(Category, cat_id) if cat_id else None
        st = float(s)
        out.append({"categoria_id": cat_id, "nombre": cat.nombre if cat else "Sin categoría",
                    "total": st, "porcentaje": round(st / total * 100, 2) if total else 0})
    return sorted(out, key=lambda x: x["total"], reverse=True)


@router.get("/simulador")
def simulador(monto: float, mes: str | None = None, categoria: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    """¿Puedo permitírmelo? Todo sale de services/finanzas.py, sin recalcular aquí."""
    if monto <= 0:
        raise HTTPException(422, "El monto debe ser mayor a 0")
    return fin.puedo_gastar(db, user.id, monto, mes or fin.mes_actual(), categoria)


@router.get("/pronostico")
def pronostico(meses: int = 6, db: Session = Depends(get_db),
               user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    """Balance esperado mes a mes: fijos declarados + promedio de variables."""
    return fin.proyeccion(db, user.id, fin.mes_actual(), max(1, min(meses, 24)))


@router.get("/escenarios")
def escenarios(aporte_mensual: float = 0, meta_id: str | None = None,
               db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    """Qué pasa si: ¿cuándo cumplo mi meta con este aporte?

    Sin meta_id devuelve todas las metas con su ruta y cuál priorizar, que es la
    respuesta útil cuando el usuario no sabe a cuál meta se refiere.
    """
    if aporte_mensual < 0:
        raise HTTPException(422, "El aporte no puede ser negativo")
    if meta_id:
        r = fin.ruta_meta(db, user.id, meta_id, aporte_mensual)
        if "error" in r:
            raise HTTPException(404, r["error"])
        return r
    metas = []
    for g in db.query(Goal).filter_by(user_id=user.id, perfil_id=perfil.id).all():
        metas.append(fin.ruta_meta(db, user.id, g.id, aporte_mensual))
    alcanzable = fin.meta_mas_alcanzable(db, user.id)
    return {"aporte_mensual": aporte_mensual, "metas": metas,
            "recomendada": alcanzable, "estimacion": True}
