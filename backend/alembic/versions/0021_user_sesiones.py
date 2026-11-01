"""Sesiones de dispositivos activos.

Permite al usuario ver en que dispositivos tiene su sesion iniciada y revocarlas.
"""
import sqlalchemy as sa
from alembic import op

revision = "0021_user_sesiones"
down_revision = "0020_dia_semana_fijo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("device_id", sa.String(64), index=True, nullable=False),
        sa.Column("device_name", sa.String(120), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("last_active_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_sessions")
