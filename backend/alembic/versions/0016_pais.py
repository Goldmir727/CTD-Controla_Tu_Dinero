"""0016 los usuarios tienen pais.

Razon: la moneda sola no alcanza. COP, USD y MXN comparten el simbolo "$", asi que
con solo el codigo de moneda cambiar de COP a USD no cambia NADA de lo que se ve
y el ajuste parece roto. Ademas el formateo estaba fijo en es-CO, de modo que un
usuario de Estados Unidos veia "$1.234.567" en vez de "$1,234,567".

El pais es lo que desambigua y ademas trae el dato estructural: si en ese pais se
cobra por quincenas o no, que es la diferencia entre una pantalla que habla de
"primera quincena de octubre" y una que no tiene porque hablar de eso.

Los usuarios existentes se rellenan desde su moneda: COP era Colombia, MXN era
Mexico, EUR era España. No es una suposicion risky: la app solo aceptaba cuatro
monedas y cada una apuntaba a un unico pais.

Revision ID: 0016_pais
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_pais"
down_revision = "0015_mov_recurrente"
branch_labels = None
depends_on = None

# Cada moneda que la app aceptaba mapeaba a un unico pais, porque solo habia
# cuatro opciones y no se confundian entre si.
MONEDA_A_PAIS = {"COP": "CO", "MXN": "MX", "USD": "US", "EUR": "ES"}


def upgrade() -> None:
    op.add_column("users", sa.Column("pais", sa.String(2), nullable=True))
    # Se usa la conexion y no op.execute porque el segundo argumento posicional de
    # op.execute es execution_options, no los parametros de la sentencia.
    conn = op.get_bind()
    for moneda, pais in MONEDA_A_PAIS.items():
        conn.execute(sa.text("UPDATE users SET pais = :p WHERE moneda = :m"),
                     {"p": pais, "m": moneda})
    conn.execute(sa.text("UPDATE users SET pais = 'CO' WHERE pais IS NULL"))
    op.create_index("ix_users_pais", "users", ["pais"])


def downgrade() -> None:
    op.drop_index("ix_users_pais", table_name="users")
    op.drop_column("users", "pais")