"""Ingresos y gastos fijos (recurrentes) - declarativos.

Version 1: el usuario marca a mano lo que es fijo. El campo `confirmado` reserva
el espacio para la autodeteccion posterior (que propondria candidatos con
confirmado=False y el usuario acepta o descarta).

No crea movimientos: es informacion de planificacion. El motor de calculo
(services/finanzas.py) la usa para separar fijos de variables y proyectar.
"""
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.models.perfil import Perfil
from app.models.finance import Account, Category
from app.models.goals import Recurring
from app.models.user import User
from app.services import finanzas as fin
from app.services.calculos import r2

router = APIRouter(tags=["fijos"])

Frecuencia = Literal["mensual", "quincenal", "semanal"]


class RecurrenteIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: Literal["ingreso", "gasto"]
    monto: float = Field(gt=0)
    dia: int = Field(default=1, ge=1, le=31)
    frecuencia: Frecuencia = "mensual"
    cuenta_id: str | None = None
    categoria_id: str | None = None
    nota: str | None = Field(default=None, max_length=255)


class RecurrentePatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    monto: float | None = Field(default=None, gt=0)
    dia: int | None = Field(default=None, ge=1, le=31)
    frecuencia: Frecuencia | None = None
    cuenta_id: str | None = None
    categoria_id: str | None = None
    nota: str | None = Field(default=None, max_length=255)
    activo: bool | None = None


def _validar_refs(db: Session, user_id: str, tipo: str,
                  cuenta_id: str | None, categoria_id: str | None) -> None:
    if cuenta_id and not db.query(Account).filter_by(id=cuenta_id, user_id=user_id).first():
        raise HTTPException(404, "Cuenta no encontrada")
    if categoria_id:
        cat = db.get(Category, categoria_id)
        if not cat or cat.user_id != user_id:
            raise HTTPException(404, "Categoría no encontrada")
        if cat.tipo not in (tipo, "ambos"):
            raise HTTPException(422, f"La categoría '{cat.nombre}' no aplica a {tipo}s")


@router.get("/recurrentes")
def listar(activo: bool | None = None, db: Session = Depends(get_db),
           user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    """Lista los fijos con su equivalencia mensual, más los totales del mes."""
    q = db.query(Recurring).filter_by(user_id=user.id, perfil_id=perfil.id)
    if activo is not None:
        q = q.filter_by(activo=activo)
    detalle = {d["id"]: d for d in fin.fijos_mensuales(db, user.id, perfil.id)["detalle"]}
    cats = {c.id: c.nombre for c in
           db.query(Category).filter_by(user_id=user.id, perfil_id=perfil.id).all()}
    items = []
    for r in q.order_by(Recurring.tipo, Recurring.nombre).all():
        d = detalle.get(r.id, {})
        items.append({
            "id": r.id, "nombre": r.nombre, "tipo": r.tipo, "monto": float(r.monto),
            "monto_mes": d.get("monto_mes", float(r.monto)), "dia": r.dia,
            "frecuencia": r.frecuencia, "activo": r.activo, "confirmado": r.confirmado,
            "cuenta_id": r.cuenta_id, "categoria_id": r.categoria_id,
            "categoria": cats.get(r.categoria_id), "nota": r.nota,
        })
    return {"items": items, "resumen": _resumen(db, user.id, perfil.id)}


def _resumen(db: Session, user_id: str, perfil_id: str, mes: str | None = None) -> dict:
    mes = mes or fin.mes_actual()
    f = fin.fijos_mensuales(db, user_id, perfil_id)
    r = fin.ratio_fijo(db, user_id, perfil_id, mes)
    return {"mes": mes, "ingresos_fijos_mes": f["ingresos_fijos_mes"],
            "gastos_fijos_mes": f["gastos_fijos_mes"], "neto_fijo_mes": f["neto_fijo_mes"],
            "cantidad": f["cantidad"], "ratio_fijo": r["ratio_fijo"],
            "gastos_variables_mes": r["gastos_variables"]}


@router.get("/recurrentes/resumen")
def resumen(mes: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
            db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    """Totales de fijos y qué porcentaje de tus gastos del mes está comprometido."""
    return _resumen(db, user.id, perfil.id, mes)


@router.get("/recurrentes/proyeccion")
def proyeccion(meses: int = 6, db: Session = Depends(get_db),
               user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    """Balance esperado mes a mes. Reutiliza el motor, no recalcula."""
    if not db.query(Recurring).filter_by(user_id=user.id, perfil_id=perfil.id).first():
        raise HTTPException(
            422,
            "Primero marca tus ingresos y gastos fijos en Plan › Fijos. "
            "Sin eso la proyección solo tendría en cuenta tu promedio.",
        )
    return fin.proyeccion(db, user.id, perfil.id, fin.mes_actual(), meses)


@router.post("/recurrentes", status_code=201)
def crear(data: RecurrenteIn, db: Session = Depends(get_db),
          user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    _validar_refs(db, user.id, data.tipo, data.cuenta_id, data.categoria_id)
    r = Recurring(user_id=user.id, perfil_id=perfil.id, nombre=data.nombre.strip(), tipo=data.tipo,
                  monto=data.monto, dia=data.dia, frecuencia=data.frecuencia,
                  cuenta_id=data.cuenta_id, categoria_id=data.categoria_id,
                  nota=data.nota, activo=True, confirmado=True)
    db.add(r)
    db.commit()
    return {"id": r.id, "monto_mes": r2(float(r.monto) * fin.FACTOR_FRECUENCIA[r.frecuencia])}


@router.patch("/recurrentes/{rec_id}")
def editar(rec_id: str, data: RecurrentePatch, db: Session = Depends(get_db),
           user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    r = db.query(Recurring).filter_by(id=rec_id, user_id=user.id, perfil_id=perfil.id).first()
    if not r:
        raise HTTPException(404, "Fijo no encontrado")
    campos = data.model_dump(exclude_unset=True)
    if "categoria_id" in campos or "tipo" in campos:
        _validar_refs(db, user.id, campos.get("tipo", r.tipo),
                      campos.get("cuenta_id", r.cuenta_id),
                      campos.get("categoria_id", r.categoria_id))
    for k, v in campos.items():
        setattr(r, k, v)
    db.commit()
    return {"id": r.id, "monto_mes": r2(float(r.monto) * fin.FACTOR_FRECUENCIA[r.frecuencia])}


@router.patch("/recurrentes/{rec_id}/toggle")
def toggle(rec_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    """Activa/desactiva sin borrar: asi un arriendo temporal se pausa, no se pierde."""
    r = db.query(Recurring).filter_by(id=rec_id, user_id=user.id, perfil_id=perfil.id).first()
    if not r:
        raise HTTPException(404, "Fijo no encontrado")
    r.activo = not r.activo
    db.commit()
    return {"id": r.id, "activo": r.activo}


@router.delete("/recurrentes/{rec_id}", status_code=204)
def borrar(rec_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    r = db.query(Recurring).filter_by(id=rec_id, user_id=user.id, perfil_id=perfil.id).first()
    if not r:
        raise HTTPException(404, "Fijo no encontrado")
    db.delete(r)
    db.commit()
