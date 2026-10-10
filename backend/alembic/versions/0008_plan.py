"""0008 plan comercial (free/pro) + indices de agregacion.

Motivo de los indices: /resumen, /presupuestos, /reportes/* y el contexto del asesor
agregan con to_char(fecha,'YYYY-MM') por user_id. Sin indice compuesto cada consulta
escanea toda la tabla del usuario.

Revision ID: 0008_plan
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_plan"
down_revision = "0007_asesor_historial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("plan", sa.String(20), nullable=False, server_default="free"))
    op.add_column("users", sa.Column("plan_desde", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("plan_vencimiento", sa.DateTime(), nullable=True))

    # Agregaciones por mes y listados de historial ordenados por fecha.
    op.create_index("ix_transactions_user_fecha", "transactions", ["user_id", "fecha"])
    op.create_index("ix_transactions_user_tipo_fecha", "transactions", ["user_id", "tipo", "fecha"])
    op.create_index("ix_budgets_user_periodo", "budgets", ["user_id", "periodo"])
    op.create_index("ix_asesor_mensajes_user_chat", "asesor_mensajes", ["user_id", "chat_id"])


def downgrade() -> None:
    op.drop_index("ix_asesor_mensajes_user_chat", table_name="asesor_mensajes")
    op.drop_index("ix_budgets_user_periodo", table_name="budgets")
    op.drop_index("ix_transactions_user_tipo_fecha", table_name="transactions")
    op.drop_index("ix_transactions_user_fecha", table_name="transactions")
    op.drop_column("plan_vencimiento", "users")
    op.drop_column("plan_desde", "users")
    op.drop_column("plan", "users")
