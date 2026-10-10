"""Perfil: ambito de las finanzas. Personal o Negocio.

Por que existe: el error clasico del independiente es mezclar la plata del negocio
con la personal. Sin un ambito explicito la app no puede avisar "estabas pagando un
gasto personal desde la caja del negocio".

Todo lo que cuelga de un perfil (cuentas, categorias, movimientos, presupuestos,
metas, fijos) lleva perfil_id NOT NULL, asi que no puede quedar nada fuera del
aislamiento.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class Perfil(UUIDBase):
    __tablename__ = "perfiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(10), default="personal")  # personal|negocio
    principal: Mapped[bool] = mapped_column(Boolean, default=True)
    notificar_mezcla: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)