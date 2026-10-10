"""0012 los UNIQUE pasan a colgar del perfil, no del usuario.

Con Personal + Negocio, un UNIQUE sobre (user_id, nombre, tipo) impide tener
"Comida" en los dos perfiles: el usuario tendria que renombrarla. Aqui la
unicidad baja al perfil, que es el ambito real del dato.

Idempotente con bloques DO: no falla si los constraints ya estan en el estado
nuevo (util cuando la migracion se reaplica sobre una base ya migrada).

Revision ID: 0012_unique_por_perfil
"""
from alembic import op

revision = "0012_unique_por_perfil"
down_revision = "0011_perfiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_cat_user_nombre_tipo') THEN
                ALTER TABLE categories DROP CONSTRAINT uq_cat_user_nombre_tipo;
                ALTER TABLE categories ADD CONSTRAINT uq_cat_perfil_nombre_tipo
                    UNIQUE (perfil_id, nombre, tipo);
            END IF;
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_budget_user_cat_periodo') THEN
                ALTER TABLE budgets DROP CONSTRAINT uq_budget_user_cat_periodo;
                ALTER TABLE budgets ADD CONSTRAINT uq_budget_perfil_cat_periodo
                    UNIQUE (perfil_id, categoria_id, periodo);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_cat_perfil_nombre_tipo') THEN
                ALTER TABLE categories DROP CONSTRAINT uq_cat_perfil_nombre_tipo;
                ALTER TABLE categories ADD CONSTRAINT uq_cat_user_nombre_tipo
                    UNIQUE (user_id, nombre, tipo);
            END IF;
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_budget_perfil_cat_periodo') THEN
                ALTER TABLE budgets DROP CONSTRAINT uq_budget_perfil_cat_periodo;
                ALTER TABLE budgets ADD CONSTRAINT uq_budget_user_cat_periodo
                    UNIQUE (user_id, categoria_id, periodo);
            END IF;
        END $$;
    """)