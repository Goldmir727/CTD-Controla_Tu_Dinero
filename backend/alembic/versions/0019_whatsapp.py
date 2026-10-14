"""Telefono en el usuario + tablas del bot de WhatsApp.

Tres cosas:

1. `users.telefono`. El usuario se identifica por correo; el bot, por numero.
   Sin esta columna no hay forma de saber de quien es "gaste 25 mil en el
   almuerzo". Es UNIQUE y nullable: unique porque un numero no puede pertenecer
   a dos cuentas (si no, uno podria ver los gastos del otro), y nullable porque
   la mayoria de la gente entra por la PWA y no tiene por que dar su numero.

2. `whatsapp_vinculos`. El vinculo verificado numero -> usuario. Vive aparte
   porque un usuario puede tener mas de un canal y cambiar de numero sin que eso
   le cambie la cuenta.

3. `whatsapp_sesiones`. La memoria de la conversacion: que propuesta espera
   confirmacion. Sin esto, el "si" que llega tres minutos despues no tendria
   contra que confirmarse.
"""
import sqlalchemy as sa
from alembic import op

revision = "0019_whatsapp"
down_revision = "0018_suscripciones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telefono", sa.String(20), nullable=True))
    op.create_index("ix_users_telefono", "users", ["telefono"], unique=True)

    op.create_table(
        "whatsapp_vinculos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("telefono", sa.String(20), nullable=False),
        sa.Column("ultimo_bot", sa.DateTime, nullable=True),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("creado", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_whatsapp_vinculos_user_id", "whatsapp_vinculos", ["user_id"])
    op.create_index("ix_whatsapp_vinculos_telefono", "whatsapp_vinculos", ["telefono"])

    op.create_table(
        "whatsapp_sesiones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("perfil_id", sa.String(36), sa.ForeignKey("perfiles.id"), nullable=False),
        sa.Column("estado", sa.String(30), nullable=False, server_default="listo"),
        sa.Column("captura_id", sa.String(36), nullable=True),
        sa.Column("propuestos", sa.Text, nullable=True),
        sa.Column("respondido", sa.String(80), nullable=True),
        sa.Column("creado", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("actualizado", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_whatsapp_sesiones_user_id", "whatsapp_sesiones", ["user_id"])
    op.create_index("ix_whatsapp_sesiones_perfil_id", "whatsapp_sesiones", ["perfil_id"])
    op.create_index("ix_wa_sesion_user_estado", "whatsapp_sesiones", ["user_id", "estado"])


def downgrade() -> None:
    op.drop_index("ix_wa_sesion_user_estado", table_name="whatsapp_sesiones")
    op.drop_index("ix_whatsapp_sesiones_perfil_id", table_name="whatsapp_sesiones")
    op.drop_index("ix_whatsapp_sesiones_user_id", table_name="whatsapp_sesiones")
    op.drop_table("whatsapp_sesiones")
    op.drop_index("ix_whatsapp_vinculos_telefono", table_name="whatsapp_vinculos")
    op.drop_index("ix_whatsapp_vinculos_user_id", table_name="whatsapp_vinculos")
    op.drop_table("whatsapp_vinculos")
    op.drop_index("ix_users_telefono", table_name="users")
    op.drop_column("users", "telefono")