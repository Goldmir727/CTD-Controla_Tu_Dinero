from datetime import date, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.models.perfil import Perfil
from app.models.finance import Account, Category, Transaction
from app.models.user import User
from app.schemas.finance import MovimientoIn, MovimientoPatch

router = APIRouter(tags=["movimientos"])


def _validar(data_tipo: str, data_fecha, cuenta_id: str, categoria_id: str | None,
             db: Session, user: User, perfil: Perfil | None = None):
    # RN-03: fecha válida, no futura más de +1 día
    if data_fecha > date.today() + timedelta(days=1):
        raise HTTPException(422, "La fecha no puede ser futura más de 1 día")
    acc = db.query(Account).filter_by(id=cuenta_id, user_id=user.id, perfil_id=perfil.id).first()
    if not acc:
        # 404 y no 422 a proposito: si dijéramos "esa cuenta es de otro perfil"
        # confirmariamos que existe. Es la misma razon por la que no se cruzan perfiles.
        raise HTTPException(404, "Cuenta no encontrada")
    if categoria_id:
        cat = db.query(Category).filter_by(id=categoria_id, user_id=user.id, perfil_id=perfil.id).first()
        if not cat:
            raise HTTPException(404, "Categoría no encontrada")
        if cat.tipo != "ambos" and cat.tipo != data_tipo:
            raise HTTPException(422, f"La categoría {cat.nombre} no admite {data_tipo}")


def _out(m: Transaction) -> dict:
    return {"id": m.id, "tipo": m.tipo, "monto": float(m.monto), "fecha": str(m.fecha),
            "descripcion": m.descripcion, "categoria_id": m.categoria_id,
            "cuenta_id": m.cuenta_id, "metodo_id": m.metodo_id}


@router.post("/movimientos", status_code=201)
def crear(
    data: MovimientoIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    perfil: Perfil = Depends(get_perfil),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key:
        prev = db.query(Transaction).filter_by(user_id=user.id, perfil_id=perfil.id,
                                                 idempotency_key=idempotency_key).first()
        if prev:
            if float(prev.monto) != data.monto or prev.tipo != data.tipo:
                raise HTTPException(409, "Idempotency-Key ya usada con otro contenido")
            return {**_out(prev), "reutilizado": True}
    _validar(data.tipo, data.fecha, data.cuenta_id, data.categoria_id, db, user, perfil)
    mov = Transaction(user_id=user.id, perfil_id=perfil.id, idempotency_key=idempotency_key, **data.model_dump())
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return _out(mov)


@router.get("/movimientos")
def listar(
    tipo: str | None = None,
    cuenta_id: str | None = None,
    categoria_id: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    q: str | None = None,
page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
user: User = Depends(get_current_user),
    perfil: Perfil = Depends(get_perfil),
):
    query = db.query(Transaction).filter_by(user_id=user.id, perfil_id=perfil.id)
    if tipo:
        query = query.filter(Transaction.tipo == tipo)
    if cuenta_id:
        query = query.filter(Transaction.cuenta_id == cuenta_id)
    if categoria_id:
        query = query.filter(Transaction.categoria_id == categoria_id)
    if desde:
        query = query.filter(Transaction.fecha >= desde)
    if hasta:
        query = query.filter(Transaction.fecha <= hasta)
    if q:
        query = query.filter(Transaction.descripcion.ilike(f"%{q}%"))
    total = query.count()
    items = query.order_by(Transaction.fecha.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_out(m) for m in items], "total": total, "page": page, "page_size": page_size}


@router.get("/movimientos/{mov_id}")
def obtener(mov_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    m = db.query(Transaction).filter_by(id=mov_id, user_id=user.id, perfil_id=perfil.id).first()
    if not m:
        raise HTTPException(404, "Movimiento no encontrado")
    return _out(m)


@router.patch("/movimientos/{mov_id}")
def actualizar(mov_id: str, data: MovimientoPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    m = db.query(Transaction).filter_by(id=mov_id, user_id=user.id, perfil_id=perfil.id).first()
    if not m:
        raise HTTPException(404, "Movimiento no encontrado")
    patch = data.model_dump(exclude_unset=True, exclude_none=False)
    # Solo aplica campos presentes (None explícito limpia categoria/metodo)
    nuevo_tipo = patch.get("tipo", m.tipo)
    # Para validación usa valores resultantes
    _validar(nuevo_tipo, patch.get("fecha", m.fecha),
             patch.get("cuenta_id", m.cuenta_id),
             patch.get("categoria_id", m.categoria_id) if "categoria_id" in patch else m.categoria_id,
             db, user)
    for k, v in patch.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return _out(m)


@router.delete("/movimientos/{mov_id}", status_code=204)
def eliminar(mov_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    m = db.query(Transaction).filter_by(id=mov_id, user_id=user.id, perfil_id=perfil.id).first()
    if not m:
        raise HTTPException(404, "Movimiento no encontrado")
    db.delete(m)
    db.commit()
    return None
