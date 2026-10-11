from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from datetime import datetime

from app.models.base import UUIDBase


class User(UUIDBase):
    __tablename__ = "users"

    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    moneda: Mapped[str] = mapped_column(String(3), default="COP")
    # El pais es lo que manda sobre el formato y sobre si la app razona en
    # quincenas. La moneda se conserva porque el usuario la elige a proposito,
    # pero el simbolo y los separadores salen del pais. Ver services/paises.py.
    pais: Mapped[str] = mapped_column(String(2), default="CO", index=True)
    foto_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # avatar data-URL
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    # Consentimiento legal (Ley 1581 de 2012). NULL = versión anterior, se pide al entrar.
    acepta_terminos_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    terminos_version: Mapped[str | None] = mapped_column(String(10), nullable=True)
    acepta_datos_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    datos_version: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Plan comercial. Activacion manual por ahora (sin pasarela de pago); la columna
    # queda lista para que el checkout future solo la actualice.
    plan: Mapped[str] = mapped_column(String(20), default="free")
    plan_desde: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    plan_vencimiento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
