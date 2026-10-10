"""0011 perfiles: separar finanzas Personales del Negocio.

Por que: el error clasico del independiente es mezclar la plata del negocio con la
personal. Sin un ambito explicito la app no puede avisar "estabas pagando algo
personal desde la caja del negocio".

- Todo usuario existente recibe un perfil "Personal" y TODAS sus filas quedan en el.
  Nadie pierde datos ni cambia de comportamiento.
- principal=true marca el perfil por defecto (el que se usa si no se indica otro).
- perfil_id queda NOT NULL: es la garantia de que no queden filas huerfanas fuera de
  un perfil, que es justo lo que romperia el aislamiento.

Revision ID: 0011_perfiles
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_perfiles"
down_revision = "0010_vocabulario_co"
branch_labels = None
depends_on = None

# El orden importa: cada tabla se puebla DESPUES de existir la columna perfil_id.
TABLAS = ["accounts", "categories", "transactions", "budgets", "goals", "recurrings"]
# payment_methods NO lleva perfil_id a proposito: una billetera Nequi es la misma
# tanto en lo personal como en el negocio.


def upgrade() -> None:
    op.create_table(
        "perfiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        # personal | negocio
        sa.Column("tipo", sa.String(10), nullable=False, server_default="personal"),
        # El perfil por defecto del usuario. Solo uno puede serlo.
        sa.Column("principal", sa.Boolean(), nullable=False, server_default=sa.true()),
        # Para el negocio: alertas si se mezclan flujos, y eventos previstos.
        sa.Column("notificar_mezcla", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_perfiles_user_principal", "perfiles", ["user_id", "principal"])
    op.create_check_constraint("ck_perfiles_tipo", "perfiles", "tipo in ('personal','negocio')")

    for t in TABLAS:
        op.add_column(t, sa.Column("perfil_id", sa.String(36), nullable=True))
        op.create_index(f"ix_{t}_perfil", t, ["perfil_id"])

    # Un perfil "Personal" por usuario. El id se genera en SQL (UUID real) y se
    # guarda el mapeo en una tabla temporal, porque los UPDATE siguientes necesitan
    # traducir user_id -> perfil_id sin volver a Python.
    op.execute("""
        CREATE TEMPORARY TABLE _perfil_map ON COMMIT DROP AS
        SELECT gen_random_uuid()::text AS pid, u.id AS uid
        FROM users u
        WHERE NOT EXISTS (SELECT 1 FROM perfiles p WHERE p.user_id = u.id)
    """)
    op.execute("""
        INSERT INTO perfiles (id, user_id, nombre, tipo, principal, notificar_mezcla)
        SELECT pid, uid, 'Personal', 'personal', true, true FROM _perfil_map
    """)
    for t in TABLAS:
        op.execute(f"""
            UPDATE {t} SET perfil_id = m.pid
            FROM _perfil_map m
            WHERE {t}.user_id = m.uid AND {t}.perfil_id IS NULL
        """)
    op.execute("DROP TABLE _perfil_map")

    # Ahora que no hay huerfanos, se vuelve NOT NULL. La FK se agrega al final.
    for t in TABLAS:
        op.alter_column(t, "perfil_id", nullable=False)
        op.create_foreign_key(f"fk_{t}_perfil", t, "perfiles", ["perfil_id"], ["id"])


def downgrade() -> None:
    for t in reversed(TABLAS):
        op.drop_constraint(f"fk_{t}_perfil", t, type_="foreignkey")
        op.drop_index(f"ix_{t}_perfil", table_name=t)
        op.drop_column(t, "perfil_id")
    op.drop_table("perfiles")