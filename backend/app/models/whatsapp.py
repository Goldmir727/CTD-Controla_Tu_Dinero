"""Datos de WhatsApp: con quien es el telefono y en que va la conversacion.

Son dos cosas distintas y por eso son dos tablas:

`Vinculo` responde "este numero de WhatsApp es que usuario". Sin esto el bot no
puede guardar nada, porque no hay forma de saber de quien es "gaste 25 mil".

`Sesion` es la memoria de una conversacion en curso: la propuesta que falta por
confirmar y hace cuanto. WhatsApp manda un mensaje cada vez, sin sesion; el
"sí" que confirma el gasto llega como un mensaje suelto tres minutos despues, y
sin guardar la propuesta pendiente no habria nada que confirmar.

Por que NO se guarda el codigo de verificacion en la tabla: vive en cache con
caducidad corta (`services/verificar.py`). En una base queda texto que alguien
puede leer y usar para vincular un numero ajeno.
"""
from datetime import datetime, timedelta

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WhatsappVinculo(Base):
    """Un numero de WhatsApp apuntado a un usuario."""

    __tablename__ = "whatsapp_vinculos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    # Solo digitos, con codigo de pais y sin +. Colombia = 57.
    telefono: Mapped[str] = mapped_column(String(20), index=True, default="")
    # Ultimo mensaje visto del bot. Se usa para la ventana de 24h de WhatsApp:
    # fuera de ella solo se pueden enviar plantillas aprobadas.
    ultimo_bot: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activo: Mapped[bool] = mapped_column(default=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WhatsappSesion(Base):
    """La conversacion en curso de un usuario: que falta por confirmar."""

    __tablename__ = "whatsapp_sesiones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    perfil_id: Mapped[str] = mapped_column(String(36), ForeignKey("perfiles.id"), index=True)
    estado: Mapped[str] = mapped_column(String(30), default="listo")
    # Id de la captura pendiente. Es lo que permite confirmar sin volver a pedir
    # la frase ni volver a gastar una llamada al modelo.
    captura_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # JSON de los movimientos propuestos, por si hay que corregirlos a mano.
    propuestos: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Mensaje_id de WhatsApp ya respondido: sirve para no repetir la misma
    # respuesta cuando Meta reintenta la entrega.
    respondido: Mapped[str | None] = mapped_column(String(80), nullable=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def expira_en(self) -> datetime:
        """Una propuesta vieja es ruido: se caduca para que el "sí" de manana
        confirme lo de hoy y no algo de hace una semana."""
        return self.actualizado + timedelta(hours=2)


Index("ix_wa_sesion_user_estado", WhatsappSesion.user_id, WhatsappSesion.estado)