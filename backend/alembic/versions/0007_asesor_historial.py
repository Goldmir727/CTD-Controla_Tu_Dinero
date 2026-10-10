"""0007 historial del asesor: chats y mensajes por usuario.

Revision ID: 0007_asesor_historial
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_asesor_historial"
down_revision = "0006_foto"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asesor_chats",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("titulo", sa.String(120), nullable=False, server_default="Chat"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "asesor_mensajes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("chat_id", sa.String(36), sa.ForeignKey("asesor_chats.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("rol", sa.String(10), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("asesor_mensajes")
    op.drop_table("asesor_chats")
