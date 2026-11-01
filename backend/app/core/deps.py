from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.perfil import Perfil
from app.models.sesion import UserSession
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falta token")
    user_id = decode_token(creds.credentials, want="access")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o vencido")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no existe")

    # Actualizar ultima actividad de la sesion de este dispositivo (si se conoce el device_id).
    if x_device_id:
        sesion = (
            db.query(UserSession)
            .filter_by(user_id=user.id, device_id=x_device_id)
            .first()
        )
        if sesion and sesion.is_active:
            sesion.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
        elif sesion and not sesion.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesion revocada en este dispositivo. Inicia sesion de nuevo.",
            )

    return user


def get_perfil(
    perfil_id: str | None = Query(default=None, description="Perfil a usar; si se omite, el principal"),
    x_perfil_id: str | None = Header(default=None, alias="X-Perfil-Id"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Perfil:
    """Resuelve el perfil activo.

    Se puede pedir por query `?perfil_id=` o por header `X-Perfil-Id`. El header es
    lo que usa el frontend: lo manda un interceptor de axios y no hay que tocar
    ninguna URL.

    Es OBLIGATORIO filtrar por perfil.id en toda lectura y escribir con
    perfil.id en toda insercion: es lo que separa lo Personal de lo Negocio.
    """
    pedido = (x_perfil_id or perfil_id or "").strip() or None
    if pedido:
        p = db.query(Perfil).filter_by(id=pedido, user_id=user.id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        return p
    p = db.query(Perfil).filter_by(user_id=user.id, principal=True).first()
    if not p:
        # Un usuario siempre tiene al menos un perfil; si falta, es dato corrupto.
        p = db.query(Perfil).filter_by(user_id=user.id).first()
        if not p:
            raise HTTPException(status_code=500, detail="El usuario no tiene ningún perfil creado")
    return p
