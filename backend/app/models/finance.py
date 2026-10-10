"""Modelos núcleo MVP: cuentas, categorías, métodos, movimientos, presupuestos."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class Account(UUIDBase):
    __tablename__ = "accounts"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    perfil_id: Mapped[str] = mapped_column(String(36), ForeignKey("perfiles.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20), default="efectivo")  # efectivo|banco|bolsa|otro
    saldo_inicial: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


class Category(UUIDBase):
    __tablename__ = "categories"
    # El UNIQUE cuelga del perfil, no del usuario: con Personal + Negocio cada uno
    # necesita su propia "Comida".
    __table_args__ = (UniqueConstraint("perfil_id", "nombre", "tipo", name="uq_cat_perfil_nombre_tipo"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    perfil_id: Mapped[str] = mapped_column(String(36), ForeignKey("perfiles.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(10), default="gasto")  # ingreso|gasto|ambos
    icono: Mapped[str] = mapped_column(String(60), default="tag")
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class PaymentMethod(UUIDBase):
    """Sin perfil_id a proposito: una billetera Nequi es la misma en lo personal
    y en el negocio, y duplicarla solo confunde al usuario."""

    __tablename__ = "payment_methods"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))


class Transaction(UUIDBase):
    __tablename__ = "transactions"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    perfil_id: Mapped[str] = mapped_column(String(36), ForeignKey("perfiles.id"), index=True)
    cuenta_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"))
    categoria_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("categories.id"), nullable=True)
    metodo_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("payment_methods.id"), nullable=True)
    tipo: Mapped[str] = mapped_column(String(10))  # ingreso|gasto
    monto: Mapped[float] = mapped_column(Numeric(14, 2))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    descripcion: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Budget(UUIDBase):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("perfil_id", "categoria_id", "periodo", name="uq_budget_perfil_cat_periodo"),)

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    perfil_id: Mapped[str] = mapped_column(String(36), ForeignKey("perfiles.id"), index=True)
    categoria_id: Mapped[str] = mapped_column(String(36), ForeignKey("categories.id"))
    monto: Mapped[float] = mapped_column(Numeric(14, 2))
    periodo: Mapped[str] = mapped_column(String(7))  # YYYY-MM
