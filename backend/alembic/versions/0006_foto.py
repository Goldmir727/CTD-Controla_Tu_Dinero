"""0006 users.foto_url (avatar data-URL).

Revision ID: 0006_foto
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_foto"
down_revision = "0005_consentimiento"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("foto_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "foto_url")
