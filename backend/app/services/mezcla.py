"""Detecta y explica la mezcla de plata entre Personal y Negocio.

Que es exactamente el problema que la app promete resolver: el independiente que
paga el mercado con la caja del negocio y al final de mes no sabe si puede.

El hallazgo NO bloquea nada: es un aviso. Bloquear dejaria al usuario sin poder
registrar el gasto real, y el gasto es real aunque este mal asignado. Ademas el
proposito es hacerlo visible, no coercitivo.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.finance import Account, Category, Transaction
from app.models.perfil import Perfil

# Categorias que casi siempre son personales aunque se paguen desde la caja.
# No es una regla dura: es la lista de donde empieza a asomar el problema.
PISTAS_PERSONALES = {"Ocio", "Familia", "Salud", "Educación", "Educacion", "Impuestos"}


def detectar(db: Session, user_id: str, perfil_negocio: str, mes: str) -> dict:
    """Buscar pagos desde cuentas del negocio con cara de gasto personal."""
    negocio = db.query(Perfil).filter_by(id=perfil_negocio, user_id=user_id).first()
    if not negocio:
        return {"perfil": None, "hay_riesgo": False, "hallazgos": [],
                "mensaje": "Crea un perfil de tipo Negocio para que CTD pueda vigilar la mezcla."}

    cats = {c.id: c.nombre for c in db.query(Category).filter_by(
        perfil_id=negocio.id).all()}
    cuentas = {a.id: a.nombre for a in db.query(Account).filter_by(
        perfil_id=negocio.id).all()}
    personal_ids = {cid for cid, nombre in cats.items()
                    if (nombre or "").strip().title() in {p.title() for p in PISTAS_PERSONALES}}

    if not personal_ids:
        return {"perfil": negocio.nombre, "hay_riesgo": False, "hallazgos": [],
                "mensaje": "Todo bien: no salió plata del negocio a gastos personales."}

    filas = db.query(
        Transaction.categoria_id,
        Transaction.cuenta_id,
        func.sum(Transaction.monto).label("total"),
        func.count(Transaction.id).label("n"),
    ).filter(
        Transaction.user_id == user_id,
        Transaction.perfil_id == negocio.id,
        Transaction.tipo == "gasto",
        Transaction.categoria_id.in_(personal_ids),
        func.to_char(Transaction.fecha, "YYYY-MM") == mes,
    ).group_by(Transaction.categoria_id, Transaction.cuenta_id).all()

    hallazgos = []
    for cat_id, cuenta_id, total, n in filas:
        hallazgos.append({
            "categoria": cats.get(cat_id, "?"),
            "cuenta": cuentas.get(cuenta_id, "?"),
            "total": float(total or 0),
            "movimientos": int(n or 0),
        })
    hallazgos.sort(key=lambda h: -h["total"])
    total = round(sum(h["total"] for h in hallazgos), 2)

    if not hallazgos:
        return {"perfil": negocio.nombre, "hay_riesgo": False, "hallazgos": [],
                "total": 0,
                "mensaje": f"En {mes} no salió plata del negocio a gastos personales."}

    return {
        "perfil": negocio.nombre,
        "mes": mes,
        "hay_riesgo": True,
        "hallazgos": hallazgos,
        "total": total,
        "mensaje": (
            f"Salieron {total} desde cuentas del negocio en gastos de tipo personal "
            f"({', '.join(h['categoria'] for h in hallazgos[:3])}). Si esas salidas son "
            f"del negocio, déjalas en el Negocio; si son tuyas, muévelas a la cuenta personal."
        ),
    }