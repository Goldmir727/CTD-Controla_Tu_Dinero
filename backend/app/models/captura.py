"""Captura: bitacora de cada frase que el usuario le pasa a la IA.

Sirve para tres cosas, no solo para guardar historial:
- Cuota diaria cuando Redis no responde (se cuenta sobre esta tabla).
- Auditoria: queda que PROPUJO el modelo y que se guardo de verdad. Sirve para
  medir la precision y ajustar el prompt con evidencia, no de memoria.
- Detectar cuando el modelo se equivoca mucho y avisarle al usuario.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDBase


class Captura(UUIDBase):
    __tablename__ = "capturas"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    perfil_id: Mapped[str] = mapped_column(String(36), ForeignKey("perfiles.id"), index=True)
    texto: Mapped[str] = mapped_column(Text)                 # lo que escribio/hablo
    transcripcion: Mapped[bool] = mapped_column(Boolean, default=False)  # venia de audio
    # propuesta | guardado | descartado | error
    estado: Mapped[str] = mapped_column(String(20), default="propuesta")
    propuestos: Mapped[str] = mapped_column(Text, default="[]")  # JSON de lo que propuso
    guardados: Mapped[int] = mapped_column(default=0)
    # Hubo que confirmar el monto a mano porque el modelo no lo leyo del texto.
    monto_dudoso: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)