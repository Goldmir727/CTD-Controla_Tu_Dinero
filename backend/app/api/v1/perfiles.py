"""Perfiles: separar las finanzas Personales de las del Negocio.

Por que existe: el error clasico del independiente y del pequenocomerciante
colombiano es mezclar la plata del negocio con la personal. Sin dos ambitos
claros, la app no puede avisar "estabas pagando con la caja del negocio algo que
no es del negocio", y los impuestos, las cuentas y las metas se vuelven un
enredo sin salida.

Un usuario siempre tiene un perfil principal. Solo ese puede borrarse, y borrar
el principal esta prohibido: sin ambito la app no sabria que mostrar.
"""
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.models.perfil import Perfil
from app.models.user import User

router = APIRouter(tags=["perfiles"])


class PerfilIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: Literal["personal", "negocio"] = "negocio"
    saldo_inicial: float = Field(default=0, ge=0)
    # Avisar si se mezcla plata de los dos ambitos.
    notificar_mezcla: bool = True


class PerfilPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    notificar_mezcla: bool | None = None


def _sembrar(db: Session, perfil: Perfil) -> None:
    """Crea la cuenta y las categorias base de un perfil nuevo.

    Se reimporta de auth para no duplicar la lista de categorias: si esa lista
    crece, este archivo tendria que crecer con ella.
    """
    from app.api.v1.auth import _sembrar_perfil

    _sembrar_perfil(db, perfil.user_id, perfil.id)


@router.get("/perfiles")
def listar(db: Session = Depends(get_db), user: User = Depends(get_current_user),
           perfil: Perfil = Depends(get_perfil)):
    """Lista los perfiles del usuario. Marca cuál está activo."""
    filas = db.query(Perfil).filter_by(user_id=user.id).order_by(
        Perfil.principal.desc(), Perfil.created_at).all()
    return {"items": [{"id": p.id, "nombre": p.nombre, "tipo": p.tipo,
                       "principal": p.principal, "notificar_mezcla": p.notificar_mezcla,
                       "activo": p.id == perfil.id}
                      for p in filas],
            "activo": perfil.id}


@router.post("/perfiles", status_code=201)
def crear(data: PerfilIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Crea un perfil nuevo (casi siempre un Negocio) con su base de cuentas y categorías."""
    if db.query(Perfil).filter_by(user_id=user.id, nombre=data.nombre.strip()).first():
        raise HTTPException(409, "Ya tienes un perfil con ese nombre")
    p = Perfil(user_id=user.id, nombre=data.nombre.strip(), tipo=data.tipo,
               principal=False, notificar_mezcla=data.notificar_mezcla)
    db.add(p)
    db.flush()
    _sembrar(db, p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "nombre": p.nombre, "tipo": p.tipo, "principal": p.principal}


@router.patch("/perfiles/{perfil_id}")
def editar(perfil_id: str, data: PerfilPatch, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    p = db.query(Perfil).filter_by(id=perfil_id, user_id=user.id).first()
    if not p:
        raise HTTPException(404, "Perfil no encontrado")
    campos = data.model_dump(exclude_unset=True)
    if "nombre" in campos:
        nombre = campos["nombre"].strip()
        if (db.query(Perfil).filter_by(user_id=user.id, nombre=nombre)
                .filter(Perfil.id != p.id).first()):
            raise HTTPException(409, "Ya tienes un perfil con ese nombre")
        campos["nombre"] = nombre
    for k, v in campos.items():
        setattr(p, k, v)
    db.commit()
    return {"id": p.id, "nombre": p.nombre, "tipo": p.tipo, "notificar_mezcla": p.notificar_mezcla}


@router.patch("/perfiles/{perfil_id}/principal")
def hacer_principal(perfil_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Deja este perfil como el que se abre por defecto. Solo uno puede serlo."""
    destino = db.query(Perfil).filter_by(id=perfil_id, user_id=user.id).first()
    if not destino:
        raise HTTPException(404, "Perfil no encontrado")
    for p in db.query(Perfil).filter_by(user_id=user.id).all():
        p.principal = (p.id == destino.id)
    db.commit()
    return {"id": destino.id, "principal": True}


@router.delete("/perfiles/{perfil_id}", status_code=204)
def borrar(perfil_id: str, confirmar: bool = False, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    """Elimina un perfil y todo lo suyo.

    Solo se puede borrar un perfil vacío o no principal. Borrar el principal
    dejaria a la cuenta sin ambito, y el usuario todavia puede perder todo lo del
    otro por un clic mal puesto.
    """
    from app.models.finance import Account, Category
    from app.models.goals import Goal, Recurring
    from app.models.finance import Transaction

    p = db.query(Perfil).filter_by(id=perfil_id, user_id=user.id).first()
    if not p:
        raise HTTPException(404, "Perfil no encontrado")
    if p.principal:
        raise HTTPException(
            422,
            "No se puede borrar tu perfil principal. Deja otro como principal primero.",
        )
    from sqlalchemy import func

    for model, etiqueta in ((Transaction, "movimientos"), (Recurring, "gastos fijos")):
        n = db.query(func.count(model.id)).filter_by(perfil_id=p.id).scalar() or 0
        if n:
            raise HTTPException(
                409,
                f"Ese perfil tiene {n} {etiqueta}. Bórralos desde el perfil antes de "
                "eliminarlo, o usa 'Reiniciar' en Ajustes para borrarlo todo.",
            )
    db.query(Goal).filter_by(perfil_id=p.id).delete()
    db.query(Category).filter_by(perfil_id=p.id).delete()
    db.query(Account).filter_by(perfil_id=p.id).delete()
    db.delete(p)
    db.commit()


@router.get("/perfiles/{perfil_id}/mezcla")
def revisar_mezcla(perfil_id: str, mes: str | None = None, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """¿Salió plata del negocio a gastos personales este mes?

    Devuelve los hallazgos con monto y categoría para que la UI pueda listarlos, y
    un mensaje ya redactado para el caso de que no quieras interpretar números.
    """
    from app.services import finanzas as fin
    from app.services import mezcla as mix

    # Sin esto, un id de otro usuario caia en "no hay perfil" y devolvia 200 con un
    # mensaje que decia "crea un Negocio". No filtraba datos, pero respondia 200 a
    # un id ajeno, que es lo mismo que decir que existe.
    if not db.query(Perfil).filter_by(id=perfil_id, user_id=user.id).first():
        raise HTTPException(404, "Perfil no encontrado")
    return mix.detectar(db, user.id, perfil_id, mes or fin.mes_actual())