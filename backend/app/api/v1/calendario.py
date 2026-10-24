"""Calendario de movimientos: el mes día por día, con lo que pasó en cada fecha
y los fijos próximos (previstos vs registrados).

Por que existe: /reportes/calendario solo devuelve totales por día y vive detrás
del plan PRO. Saber qué gastaste un martes no es un reporte avanzado, es la
mitad de "revisar mis movimientos", así que este endpoint es gratis y devuelve
los movimientos de verdad, no solo la suma.

Además: trae los fijos que debían caer en ese periodo, marcados como
"previstos" (no tienen movimiento registrado) o "registrados" (el movimiento
ya está en la tabla de transacciones). Esto permite ver la agenda completa
sin duplicar cifras.
"""
from calendar import monthrange
from datetime import date
import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.models.finance import Account, Category, Transaction
from app.models.goals import Recurring
from app.models.perfil import Perfil
from app.models.user import User
from app.services import finanzas as fin
from app.services import recurrencia as recu

router = APIRouter(tags=["calendario"])


@router.get("/calendario")
def calendario(mes: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
               db: Session = Depends(get_db), user: User = Depends(get_current_user),
               perfil: Perfil = Depends(get_perfil)):
    mes = mes or fin.mes_actual()
    if mes and not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", mes):
        from fastapi import HTTPException
        raise HTTPException(422, "Formato de mes inválido, use YYYY-MM")
    """Un mes completo con sus movimientos agrupados por día y fivos próximos.

    Devuelve TODOS los días del mes (también los vacíos) porque el calendario
    los necesita para dibujar la cuadrícula; `inicio_semana` dice en qué columna
    cae el día 1 (0 = lunes), y así el front no tiene que repetir el cálculo.

    Para cada día incluye:
      - ingresos / gastos / balance de movimientos reales
      - fijos_previstos: fijos que debían caer ese día (sin movimiento aún)
      - fijos_registrados: fijos que ya tienen movimiento en ese día
    """
    mes = mes or fin.mes_actual()
    anio, mes_num = int(mes[:4]), int(mes[5:7])
    ultimo = monthrange(anio, mes_num)[1]

    categorias = {c.id: c.nombre for c in
                  db.query(Category).filter_by(user_id=user.id, perfil_id=perfil.id).all()}
    cuentas = {a.id: a.nombre for a in
               db.query(Account).filter_by(user_id=user.id, perfil_id=perfil.id).all()}

    filas = db.query(Transaction).filter(
        Transaction.user_id == user.id, Transaction.perfil_id == perfil.id,
        Transaction.fecha >= date(anio, mes_num, 1),
        Transaction.fecha <= date(anio, mes_num, ultimo),
    ).order_by(Transaction.fecha, Transaction.id).all()

    dias: dict[int, dict] = {}
    for d in range(1, ultimo + 1):
        dias[d] = {"dia": d, "ingresos": 0.0, "gastos": 0.0, "balance": 0.0,
                   "movimientos": [], "fijos_previstos": [], "fijos_registrados": []}

    for t in filas:
        fila = dias[t.fecha.day]
        monto = float(t.monto)
        if t.tipo == "ingreso":
            fila["ingresos"] = round(fila["ingresos"] + monto, 2)
        else:
            fila["gastos"] = round(fila["gastos"] + monto, 2)
        fila["movimientos"].append({
            "id": t.id, "tipo": t.tipo, "monto": monto,
            "descripcion": t.descripcion or "",
            "categoria": categorias.get(t.categoria_id),
            "cuenta": cuentas.get(t.cuenta_id),
        })

    # --- Fijos que debían caer este mes ---
    user_id = user.id
    perfil_id = perfil.id
    fijos = db.query(Recurring).filter_by(user_id=user_id, perfil_id=perfil_id, activo=True).all()
    desde = date(anio, mes_num, 1)
    hasta = date(anio, mes_num, ultimo)

    # Calcular ocurrencias reales usando el calendario normalizado
    for r in fijos:
        fechas = recu.ocurrencias(desde, hasta, r.frecuencia, r.dia, r.dia_semana)
        for f in fechas:
            dia = f.day
            fila = dias[dia]
            # Determinar si ya está registrado en transacciones
            ya_registrado = any(
                t.fecha.day == dia and t.tipo == r.tipo
                for t in filas if t.tipo == r.tipo  # filtro rápido
            )
            # Verificación más precisa: mirar si hay movimiento exacto para ese día
            # (usando monto como heurística, pero siendo conservador: si hay movimiento
            # del mismo tipo en ese día, lo consideramos "registrado", no "previsto")
            tiene_movimiento = any(
                t.fecha.day == dia and t.tipo == r.tipo and abs(float(t.monto) - float(r.monto)) < 0.01
                for t in filas
            )

            info = {
                "id": r.id, "nombre": r.nombre, "tipo": r.tipo,
                "monto": float(r.monto), "frecuencia": r.frecuencia,
                "etiqueta": recu.etiqueta(r.frecuencia, r.dia, r.dia_semana),
            }
            if tiene_movimiento:
                fila["fijos_registrados"].append(info)
            else:
                fila["fijos_previstos"].append(info)

    for fila in dias.values():
        fila["balance"] = round(fila["ingresos"] - fila["gastos"], 2)

    lista = [dias[d] for d in range(1, ultimo + 1)]
    dias_con_movimiento = sum(1 for d in lista if d["movimientos"])
    dias_con_fijos = sum(1 for d in lista if d["fijos_previstos"] or d["fijos_registrados"])

    return {
        "mes": mes,
        "anio": anio,
        "mes_num": mes_num,
        "ultimo_dia": ultimo,
        "inicio_semana": date(anio, mes_num, 1).weekday(),
        "dias": lista,
        "dias_con_movimiento": dias_con_movimiento,
        "dias_con_fijos": dias_con_fijos,
        "totales": {
            "ingresos": round(sum(d["ingresos"] for d in lista), 2),
            "gastos": round(sum(d["gastos"] for d in lista), 2),
        },
        # Resumen de fijos para el front
        "resumen_fijos": {
            "total_previstos": len([f for d in lista for f in (d["fijos_previstos"] or [])]),
            "total_registrados": len([f for d in lista for f in (d["fijos_registrados"] or [])]),
        },
    }