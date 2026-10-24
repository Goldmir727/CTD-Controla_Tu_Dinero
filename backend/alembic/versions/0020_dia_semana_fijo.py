"""Dia de la semana de un fijo semanal.

`recurrings.dia` es un dia del mes (1-31) y no alcanza para "me pagan cada
domingo": un domingo no es un dia del mes, y anclar el pago al 18 lo hacia caer
en miercoles el mes siguiente. `dia_semana` (0=lunes .. 6=domingo) solo aplica
cuando la frecuencia es semanal.

Nullable a proposito: los fijos semanales que ya existen siguen funcionando con
el dia del mes como ancla; el usuario puede cambiarlos a un dia de la semana
cuando quiera.
"""
import sqlalchemy as sa
from alembic import op

revision = "0020_dia_semana_fijo"
down_revision = "0019_whatsapp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recurrings", sa.Column("dia_semana", sa.Integer, nullable=True))
    op.create_check_constraint(
        "ck_recurring_dia_semana", "recurrings",
        "dia_semana is null or (dia_semana between 0 and 6)")


def downgrade() -> None:
    op.drop_constraint("ck_recurring_dia_semana", "recurrings", type_="check")
    op.drop_column("recurrings", "dia_semana")
