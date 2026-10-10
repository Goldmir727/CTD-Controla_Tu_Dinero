"""Modismos: termino coloquial -> categoria. Tabla GLOBAL (no por usuario)."""
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class Modismo(UUIDBase):
    __tablename__ = "modismos"

    termino: Mapped[str] = mapped_column(String(80), index=True)
    categoria: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(10), default="gasto")  # gasto|ingreso|ambos
    prioridad: Mapped[int] = mapped_column(Integer, default=10)
    nota: Mapped[str | None] = mapped_column(String(255), nullable=True)