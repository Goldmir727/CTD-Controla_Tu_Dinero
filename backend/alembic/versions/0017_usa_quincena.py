"""Quincena como preferencia del usuario.

Por que una columna y no usar el pais: el pais ya no decide el periodo de la
revision. Se calcula sobre el MES por defecto y quien cobre por quincena lo
activa en Ajustes.

El default es False a proposito: la app habla en meses desde el primer dia, que es
lo que espera la mayoria. Dejar True obligaba a toda la base a cambiar de forma
silenciosa al desplegar esto.
"""
import sqlalchemy as sa
from alembic import op

revision = "0017_usa_quincena"
down_revision = "0016_pais"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("usa_quincena", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "usa_quincena")