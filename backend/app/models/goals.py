"""Metas (Opción A: solo seguimiento, RN-09) + tablas reservadas Fase 2."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class Goal(UUIDBase):
    __tablename__ = "goals"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    perfil_id: Mapped[str] = mapped_column(String(36), ForeignKey("perfiles.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    objetivo: Mapped[float] = mapped_column(Numeric(14, 2))
    fecha_objetivo: Mapped[date | None] = mapped_column(Date, nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # data-URL (foto meta) o URL externa


class GoalAporte(UUIDBase):
    __tablename__ = "goal_aportes"

    goal_id: Mapped[str] = mapped_column(String(36), ForeignKey("goals.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    monto: Mapped[float] = mapped_column(Numeric(14, 2))
    fecha: Mapped[date] = mapped_column(Date, default=date.today)
    idempotency_key: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Habit(UUIDBase):
    """Reservada Fase 2, sin lógica MVP."""

    __tablename__ = "habits"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    nombre: Mapped[str] = mapped_column(String(120), default="")


class Recurring(UUIDBase):
    """Ingreso o gasto fijo (arriendo, nomina, suscripciones...).

    Version declarativa: el usuario los marca a mano. El campo `confirmado`
    reserva el espacio para la autodeteccion posterior, que propondria
    candidatos con confirmado=False.
    """

    __tablename__ = "recurrings"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    perfil_id: Mapped[str] = mapped_column(String(36), ForeignKey("perfiles.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(10))  # ingreso | gasto
    monto: Mapped[float] = mapped_column(Numeric(14, 2))
    cuenta_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=True)
    categoria_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("categories.id"), nullable=True)
    dia: Mapped[int] = mapped_column(Integer, default=1)  # 1-31
    frecuencia: Mapped[str] = mapped_column(String(10), default="mensual")  # mensual|quincenal|semanal
    confirmado: Mapped[bool] = mapped_column(Boolean, default=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    nota: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
