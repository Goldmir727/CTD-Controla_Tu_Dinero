"""Gestion de sesiones de dispositivo.

Endpoints:
  GET    /auth/sesiones        Lista las sesiones activas del usuario logueado.
  DELETE /auth/sesiones/{id}   Revoca una sesion (cualquiera del usuario).
  DELETE /auth/sesiones/me     Revoca la sesion actual (logout de este dispositivo).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.sesion import UserSession
from app.models.user import User
from app.schemas.auth import SesionOut

router = APIRouter(tags=["auth"])


def _sesion_out(s: UserSession, es_actual: bool) -> SesionOut:
    return SesionOut(
        id=s.id,
        device_id=s.device_id,
        device_name=s.device_name,
        ip_address=s.ip_address,
        user_agent=s.user_agent,
        is_active=s.is_active,
        last_active_at=s.last_active_at,
        created_at=s.created_at,
        expires_at=s.expires_at,
        es_actual=es_actual,
    )


@router.get("/auth/sesiones", response_model=list[SesionOut])
def listar_sesiones(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista todas las sesiones del usuario, marcando la actual."""
    sesiones = (
        db.query(UserSession)
        .filter_by(user_id=user.id)
        .order_by(UserSession.last_active_at.desc().nullslast(), UserSession.created_at.desc())
        .all()
    )
    device_id_actual = request.headers.get("x-device-id")
    return [
        _sesion_out(s, es_actual=(s.device_id == device_id_actual))
        for s in sesiones
    ]


@router.delete("/auth/sesiones/{sesion_id}", status_code=status.HTTP_204_NO_CONTENT)
def revocar_sesion(
    sesion_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revoca (desactiva) una sesion del usuario."""
    s = db.query(UserSession).filter_by(id=sesion_id, user_id=user.id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    s.is_active = False
    db.commit()
    return None


@router.delete("/auth/sesiones/me", status_code=status.HTTP_204_NO_CONTENT)
def revocar_sesion_actual(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revoca la sesion del dispositivo actual (logout de este dispositivo)."""
    device_id = request.headers.get("x-device-id")
    if not device_id:
        raise HTTPException(status_code=400, detail="Falta el identificador de dispositivo")
    s = db.query(UserSession).filter_by(user_id=user.id, device_id=device_id).first()
    if s:
        s.is_active = False
        db.commit()
    return None
