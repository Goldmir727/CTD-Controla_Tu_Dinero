"""0015 los movimientos pueden decir a que fijo pertenecen.

Razon: sin esto, declarar un fijo y capturar "pague el arriendo" son dos hechos
sueltos. El motor sabe cuanto se proyecta de gasto fijo, pero no sabe si ya se
pago: no hay forma de decir "el arriendo de este mes ya esta".

Esta columna es lo que permite:
  - Preguntar "este gasto es el Arriendo que ya tienes o uno distinto?" al
    capturar, y enlazarlo si el usuario dice que si (ver services/deteccion.py).
  - Ver despues, en /plan, cuales fijos ya se pagaron y cuales faltan, sin que
    el motor tenga que adivinar comparando montos.

Es nullable y sin borrado en cascada a proposito: un movimiento de un fijo
borrado se queda, solo pierde el enlace. Perder el historial de lo que se pago
seria peor que un enlace huerfano.

Revision ID: 0015_mov_recurrente
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_mov_recurrente"
down_revision = "0014_chats_por_perfil"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("recurrente_id", sa.String(36), nullable=True))
    op.create_index("ix_transactions_recurrente_id", "transactions", ["recurrente_id"])
    # SIN foreign key a proposito, y no por descuido:
    # en el Postgres de Aiven (PgBouncer) "ALTER TABLE transactions ADD CONSTRAINT
    # ... REFERENCES recurrings (id)" falla con 'relation "recurings" does not
    # exist" aunque SELECT sobre recurrings funcione y el usuario sea su dueno con
    # REFERENCES concedido. Se comprobo con 4 intentos identicos: falla siempre.
    #
    # Que integridad NO la pone la base, la pone el codigo: toda lectura y toda
    # escritura filtra por user_id + perfil_id, y `recurrente_id` se valida contra
    # el perfil al enlazar (ver api/v1/recurrentes.py). Si se migra a un Postgres
    # propio, anadir aqui:
    #   op.create_foreign_key("fk_transactions_recurrente", "transactions",
    #                         "recurings", ["recurrente_id"], ["id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_recurrente_id", table_name="transactions")
    op.drop_column("transactions", "recurrente_id")