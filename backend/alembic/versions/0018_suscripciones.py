"""Tabla de suscripciones PRO.

Por que una tabla y no leer `users.plan`: el cobro vive en Wompi y la app necesita
contestar "¿es PRO?" sin llamar a la pasarela en cada pantalla. Ademas el estado
"cancelo pero le queda mes pagado" no cabe en dos columnas de `users`.
"""
import sqlalchemy as sa
from alembic import op

revision = "0018_suscripciones"
down_revision = "0017_usa_quincena"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suscripciones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente"),
        sa.Column("referencia", sa.String(64), nullable=False, server_default=""),
        sa.Column("wompi_reference", sa.String(80), nullable=True),
        sa.Column("monto", sa.Integer, nullable=False, server_default="0"),
        sa.Column("inicia", sa.Date, nullable=True),
        sa.Column("vence", sa.Date, nullable=True),
        sa.Column("cancela", sa.Date, nullable=True),
        sa.Column("ultimo_evento", sa.String(120), nullable=True),
        sa.Column("creado", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_suscripciones_user_id", "suscripciones", ["user_id"])
    op.create_index("ix_suscripciones_referencia", "suscripciones", ["referencia"])


def downgrade() -> None:
    op.drop_index("ix_suscripciones_referencia", table_name="suscripciones")
    op.drop_index("ix_suscripciones_user_id", table_name="suscripciones")
    op.drop_table("suscripciones")