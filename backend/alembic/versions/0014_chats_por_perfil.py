"""0014 los chats del asesor pasan a ser por perfil.

Razon: si el historial fuera solo del usuario, al cambiar de Negocio a Personal se
verian los chats del negocio y el contexto mezclaria ambos mundos. El asesor
razona sobre los numeros del perfil activo, asi que su memoria tambien debe ser
del perfil.

Sin perdida: cada chat existente se asigna al perfil principal del usuario.

Revision ID: 0014_chats_por_perfil
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_chats_por_perfil"
down_revision = "0013_capturas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("asesor_chats", sa.Column("perfil_id", sa.String(36), nullable=True))
    op.execute("""
        UPDATE asesor_chats a
        SET perfil_id = p.id
        FROM perfiles p
        WHERE p.user_id = a.user_id AND p.principal = true
    """)
    # Si un usuario se quedo sin perfil principal (no deberia pasar), cae al suyo.
    op.execute("""
        UPDATE asesor_chats a
        SET perfil_id = (
            SELECT min(p2.id) FROM perfiles p2 WHERE p2.user_id = a.user_id
        )
        WHERE a.perfil_id IS NULL
    """)
    op.execute("DELETE FROM asesor_chats WHERE perfil_id IS NULL")
    op.alter_column("asesor_chats", "perfil_id", nullable=False)
    op.create_index("ix_asesor_chats_perfil", "asesor_chats", ["perfil_id"])
    op.create_foreign_key("fk_asesor_chats_perfil", "asesor_chats", "perfiles", ["perfil_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_asesor_chats_perfil", "asesor_chats", type_="foreignkey")
    op.drop_index("ix_asesor_chats_perfil", table_name="asesor_chats")
    op.drop_column("asesor_chats", "perfil_id")