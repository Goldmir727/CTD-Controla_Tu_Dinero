"""Suscripcion PRO: lo que la app cree que Paso, no lo que Wompi creo.

Wompi es la fuente de la verdad del COBRO, pero no alcanza para responder
"este usuario es PRO?". Eso lo decide esta tabla, porque la app tiene que poder
decirlo sin llamar a la pasarela en cada pagina, y porque al cancelar hay que
respetar lo que ya pago: el acceso sigue hasta que acaba el periodo.

Estados:
  pendiente  = se genero el enlace de pago, todavia no hay cobro confirmado
  activa     = PRO vigente; `vence` es cuando pierde el acceso
  cancelada  = el usuario la cancelo; sigue activa hasta `vence`
  vencida    = paso `vence` sin renovacion

`wompi_reference` evita cobrarnos dos veces el mismo evento: Wompi reintenta
entregas y un webhook puede llegar repetido.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Suscripcion(Base):
    __tablename__ = "suscripciones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    # Referencia del checkout de Wompi: es lo que permite casar el webhook.
    referencia: Mapped[str] = mapped_column(String(64), index=True, default="")
    # Ultimo evento aplicado, para no procesar dos veces el mismo cobro.
    wompi_reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    monto: Mapped[int] = mapped_column(default=0)
    inicia: Mapped[date | None] = mapped_column(Date, nullable=True)
    vence: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancela: Mapped[date | None] = mapped_column(Date, nullable=True)
    ultimo_evento: Mapped[str | None] = mapped_column(String(120), nullable=True)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)