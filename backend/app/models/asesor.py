from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class AsesorChat(UUIDBase):
    __tablename__ = "asesor_chats"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    titulo: Mapped[str] = mapped_column(String(120), default="Chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AsesorMensaje(UUIDBase):
    __tablename__ = "asesor_mensajes"

    chat_id: Mapped[str] = mapped_column(String(36), ForeignKey("asesor_chats.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    rol: Mapped[str] = mapped_column(String(10))  # user|assistant
    contenido: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
