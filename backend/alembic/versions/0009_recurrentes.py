"""0009 recurrentes: ingresos y gastos fijos declarativos.

La tabla recurrings se creo vacia en 0001 ("reservada Fase 2") y se reutiliza aqui.
Se ignoran sus filas placeholders (user_id NULL) y se reconstruye con datos reales.
decision de producto: declarativos primero (el usuario marca "esto es fijo"),
autodeteccion en fase posterior.

Revision ID: 0009_recurrentes
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_recurrentes"
down_revision = "0008_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # La tabla de 0001 solo tiene id/user_id/descripcion y no sirve: se reemplaza.
    op.execute("DELETE FROM recurrings")
    op.drop_table("recurrings")
    op.create_table(
        "recurrings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),            # ingreso | gasto
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("cuenta_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("categoria_id", sa.String(36), sa.ForeignKey("categories.id"), nullable=True),
        # dia de cobro/pago: 1-31. Para semanal/quincenal se usa como ancla.
        sa.Column("dia", sa.Integer(), nullable=False, server_default="1"),
        # frecuencia: mensual | quincenal | semanal
        sa.Column("frecuencia", sa.String(10), nullable=False, server_default="mensual"),
        # True = el usuario lo declaro fijo a mano. False = lo detecto el sistema
        # (fase posterior) y el usuario todavia no lo confirmo.
        sa.Column("confirmado", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("nota", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_recurrentes_user_activo", "recurrings", ["user_id", "activo"])
    op.create_index("ix_recurrentes_user_tipo", "recurrings", ["user_id", "tipo"])
    # Check del monto positivo: un "fijo" de 0 o negativo no tiene sentido.
    op.create_check_constraint("ck_recurrentes_monto_pos", "recurrings", "monto > 0")
    op.create_check_constraint("ck_recurrentes_tipo", "recurrings", "tipo in ('ingreso','gasto')")
    op.create_check_constraint("ck_recurrentes_frec", "recurrings",
                               "frecuencia in ('mensual','quincenal','semanal')")


def downgrade() -> None:
    op.drop_table("recurrings")
    # Se restaura la tabla original de 0001 para que el downgrade sea fiel.
    op.create_table(
        "recurrings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=False, server_default=""),
    )
