"""Sesiones de dispositivos activos de un usuario.

Rastrea en qué dispositivos (navegadores / apps instaladas) tiene el usuario
su sesion iniciada, para poder listarlas y revocarlas desde Ajustes.

Cada dispositivo genera su propio `device_id` (UUID) que guarda en localStorage
y lo envia en cada petición por el header `X-Device-Id`. El backend lo usa para
actualizar `last_active_at` y, al revocar una sesion, marca `is_active = False`.

Los JWT siguen siendo stateless y validos hasta su expiracion (access: 30 min,
refresh: 7 dias). Revocar una sesion invalida el refresh token desde el servidor
y marca la sesion como inactiva; el access token vigente expira por si solo en
pocos minutos.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase


class UserSession(UUIDBase):
    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship("User", lazy="selectin")
