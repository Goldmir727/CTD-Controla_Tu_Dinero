from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.models.perfil import Perfil
from app.models.finance import Account, Transaction
from app.models.user import User
from app.schemas.finance import CuentaDividirIn, CuentaIn, CuentaOut, CuentaPatch
from app.services.calculos import saldo_actual

router = APIRouter(tags=["cuentas"])


def _saldo(db: Session, acc: Account) -> float:
    ing = db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter_by(cuenta_id=acc.id, tipo="ingreso").scalar() or 0
    gas = db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter_by(cuenta_id=acc.id, tipo="gasto").scalar() or 0
    return saldo_actual(float(acc.saldo_inicial), float(ing), float(gas))


@router.get("/cuentas", response_model=list[CuentaOut])
def listar(db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    accs = db.query(Account).filter_by(user_id=user.id).all()
    return [CuentaOut(id=a.id, nombre=a.nombre, tipo=a.tipo, saldo_inicial=float(a.saldo_inicial), saldo_actual=_saldo(db, a)) for a in accs]


@router.post("/cuentas", response_model=CuentaOut, status_code=201)
def crear(data: CuentaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    acc = Account(user_id=user.id, perfil_id=perfil.id, **data.model_dump())
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return CuentaOut(id=acc.id, nombre=acc.nombre, tipo=acc.tipo, saldo_inicial=float(acc.saldo_inicial), saldo_actual=float(acc.saldo_inicial))


@router.delete("/cuentas/{cuenta_id}", status_code=204)
def eliminar(cuenta_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    acc = db.query(Account).filter_by(id=cuenta_id, user_id=user.id).first()
    if not acc:
        raise HTTPException(404, "Cuenta no encontrada")
    n = db.query(Transaction).filter_by(cuenta_id=cuenta_id).count()
    if n > 0 or abs(_saldo(db, acc)) > 0.01:
        raise HTTPException(409, "Transfiere o elimina movimientos primero")
    db.delete(acc)
    db.commit()
    return None


@router.patch("/cuentas/{cuenta_id}", response_model=CuentaOut)
def actualizar(cuenta_id: str, data: CuentaPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    acc = db.query(Account).filter_by(id=cuenta_id, user_id=user.id).first()
    if not acc:
        raise HTTPException(404, "Cuenta no encontrada")
    patch = data.model_dump(exclude_unset=True)
    if "saldo_inicial" in patch:
        # Solo sin movimientos (onboarding). Con movimientos usa un ingreso/gasto.
        if db.query(Transaction).filter_by(cuenta_id=cuenta_id).count() > 0:
            raise HTTPException(409, "Con movimientos, ajusta con un ingreso o gasto")
    for k, v in patch.items():
        setattr(acc, k, v)
    db.commit()
    db.refresh(acc)
    return CuentaOut(id=acc.id, nombre=acc.nombre, tipo=acc.tipo, saldo_inicial=float(acc.saldo_inicial), saldo_actual=_saldo(db, acc))


@router.post("/cuentas/dividir", response_model=CuentaOut, status_code=201)
def dividir(data: CuentaDividirIn, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    """Arrepentimiento: crea cuenta restando del total original. Sin cálculos del cliente."""
    origen = db.query(Account).filter_by(id=data.origen_id, user_id=user.id).first()
    if not origen:
        raise HTTPException(404, "Cuenta origen no encontrada")
    if db.query(Transaction).filter_by(cuenta_id=origen.id).count() > 0:
        raise HTTPException(409, "La cuenta origen ya tiene movimientos: crea la cuenta con 0 y usa un gasto/ingreso para mover el dinero")
    if float(origen.saldo_inicial) < data.monto:
        raise HTTPException(422, "El monto supera el disponible de la cuenta origen")
    origen.saldo_inicial = float(origen.saldo_inicial) - data.monto
    nueva = Account(user_id=user.id, perfil_id=perfil.id, nombre=data.nombre, tipo=data.tipo, saldo_inicial=data.monto)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return CuentaOut(id=nueva.id, nombre=nueva.nombre, tipo=nueva.tipo, saldo_inicial=float(nueva.saldo_inicial), saldo_actual=float(nueva.saldo_inicial))
