"""0013 bitacora de capturas en lenguaje natural.

Existe por tres razones, no solo por historial:
- La cuota diaria se cuenta sobre esta tabla cuando Redis no responde.
- Auditoria: queda que PROPUJO el modelo vs que se guardo, para medir precision
  con evidencia en vez de de memoria.
- Detectar cuando el modelo se equivoca seguido y avisarle al usuario.

Revision ID: 0013_capturas
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_capturas"
down_revision = "0012_unique_por_perfil"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capturas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("perfil_id", sa.String(36), sa.ForeignKey("perfiles.id"), nullable=False, index=True),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("transcripcion", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("estado", sa.String(20), nullable=False, server_default="propuesta"),
        sa.Column("propuestos", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("guardados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("monto_dudoso", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    # La cuota diaria filtra por user_id + created_at del dia.
    op.create_index("ix_capturas_user_fecha", "capturas", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("capturas")