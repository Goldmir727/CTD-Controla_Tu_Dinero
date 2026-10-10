from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.perfil import Perfil
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Falta token")
    # want="access" es obligatorio: sin esto un refresh token (7 días) se acepta como
    # credencial y salta el TTL de 30 min del access token.
    user_id = decode_token(creds.credentials, want="access")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o vencido")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no existe")
    return user


def get_perfil(
    perfil_id: str | None = Query(default=None, description="Perfil a usar; si se omite, el principal"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Perfil:
    """Resuelve el perfil activo.

    Es OBLIGATORIO filtrar por perfil.id en toda lectura y escribir con
    perfil.id en toda insercion: es lo que separa lo Personal de lo Negocio.
    """
    if perfil_id:
        p = db.query(Perfil).filter_by(id=perfil_id, user_id=user.id).first()
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
