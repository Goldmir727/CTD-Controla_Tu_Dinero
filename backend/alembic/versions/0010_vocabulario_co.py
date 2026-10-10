"""0010 vocabulario colombiano: metodos de pago, categorias nuevas y diccionario de modismos.

- SEED_METODOS se amplia con lasCarteras que mas se usan en Colombia.
- Se anaden categorias que faltaban (Servicios, Mercado, Familia, Impuestos).
- Los usuarios que YA existen reciben tambien las filas nuevas: cambiar solo el
  seed de auth.py dejaria a la gente vieja sin Nequi ni Servicios.
- modismos es un diccionario GLOBAL (no por usuario) porque el habla es la misma:
  termino -> categoria destino. Sirve para clasificar sin gastar IA.

Revision ID: 0010_vocabulario_co
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_vocabulario_co"
down_revision = "0009_recurrentes"
branch_labels = None
depends_on = None

METODOS_NUEVOS = ["Nequi", "Daviplata", "Dale", "PSE", "Nómina"]
CATEGORIAS_NUEVAS = [
    ("Servicios", "gasto", "lightning-charge"),   # luz, agua, internet, gas
    ("Mercado", "gasto", "basket"),                # supermercado
    ("Familia", "gasto", "people"),
    ("Impuestos", "gasto", "file-earmark-text"),
]

# (termino, categoria, tipo, prioridad, nota)
# Un termino puede mapear a varias categorias segun el contexto ("corrientazo" es
# un almuerzo en restaurante casi siempre, pero si el texto menciona mercado es
# compra para el almuerzo). Gana la de mayor prioridad; el resto sirve de pista.
MODISMOS = [
    ("corrientazo", "Comida", "gasto", 10, "almuerzo del dia en restaurante popular"),
    ("corrientazo", "Mercado", "gasto", 1, "compra para el almuerzo en el mercado"),
    ("lucas", "Otros", "ambos", 10, "unidad monetaria: x1000"),
    ("plata", "Otros", "ambos", 5, "nombre de la plata"),
    ("bomba", "Transporte", "gasto", 10, "gasolina"),
    ("taxi", "Transporte", "gasto", 10, None),
    ("uber", "Transporte", "gasto", 10, None),
    ("diablo", "Transporte", "gasto", 10, None),
    ("chirimbolo", "Ocio", "gasto", 10, None),
    ("borracho", "Ocio", "gasto", 10, "salir a tomar"),
    ("piche", "Ocio", "gasto", 10, None),
    ("pindah", "Ocio", "gasto", 10, None),
    ("recibo de la luz", "Servicios", "gasto", 10, None),
    ("recibo del agua", "Servicios", "gasto", 10, None),
    ("recibo", "Servicios", "gasto", 5, "recibo de un servicio"),
    ("internet", "Servicios", "gasto", 10, "fibra optica"),
    ("fibra", "Servicios", "gasto", 10, None),
    ("gas", "Servicios", "gasto", 10, "gas natural"),
    ("arriendo", "Vivienda", "gasto", 10, None),
    ("alquiler", "Vivienda", "gasto", 10, None),
    ("hipoteca", "Vivienda", "gasto", 10, None),
    ("cuota", "Vivienda", "gasto", 5, "cuota de tarjeta o prestamo"),
    ("prestamo", "Otros", "ambos", 5, None),
    ("quincena", "Salario", "ingreso", 10, "pago cada 15 dias"),
    ("nomina", "Salario", "ingreso", 10, None),
    ("salario", "Salario", "ingreso", 10, None),
    ("prima", "Salario", "ingreso", 10, "prima de junio o diciembre"),
    ("servicio", "Servicios", "gasto", 10, None),
    ("medicina", "Salud", "gasto", 10, None),
    ("farmacia", "Salud", "gasto", 10, None),
    ("doctor", "Salud", "gasto", 10, None),
    ("universidad", "Educación", "gasto", 10, None),
    ("colegio", "Educación", "gasto", 10, None),
    ("matricula", "Educación", "gasto", 10, None),
    ("mercado", "Mercado", "gasto", 10, "supermercado"),
    ("supermercado", "Mercado", "gasto", 10, None),
    ("pesqueria", "Mercado", "gasto", 10, None),
    ("tienda", "Mercado", "gasto", 5, None),
    ("reparacion", "Otros", "gasto", 5, None),
    ("pintura", "Vivienda", "gasto", 10, "pintura de casa"),
    ("aseo", "Familia", "gasto", 10, "aseadora o niñera"),
    ("niñera", "Familia", "gasto", 10, None),
    ("papeleria", "Educación", "gasto", 10, None),
    ("renta", "Impuestos", "gasto", 10, None),
]


def upgrade() -> None:
    op.create_table(
        "modismos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("termino", sa.String(80), nullable=False),
        sa.Column("categoria", sa.String(120), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False, server_default="gasto"),
        sa.Column("prioridad", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("nota", sa.String(255), nullable=True),
    )
    # NO es unico: un termino puede tener varias categorias (ver corrientazo).
    op.create_index("ix_modismos_termino", "modismos", ["termino"])

    # Aplica a los usuarios existentes. Los ids los genera la app, aqui se arma
    # el UUID en SQL con gen_random_uuid() (Aiven Postgres lo trae de serie).
    op.execute("""
        INSERT INTO payment_methods (id, user_id, nombre)
        SELECT gen_random_uuid()::text, u.id, m
        FROM users u
        CROSS JOIN (VALUES ('Nequi'), ('Daviplata'), ('Dale'), ('PSE'), ('Nómina')) AS v(m)
        WHERE NOT EXISTS (
            SELECT 1 FROM payment_methods pm
            WHERE pm.user_id = u.id AND lower(pm.nombre) = lower(v.m)
        )
    """)
    op.execute("""
        INSERT INTO categories (id, user_id, nombre, tipo, icono, activa)
        SELECT gen_random_uuid()::text, u.id, c.nombre, c.tipo, c.icono, true
        FROM users u
        CROSS JOIN (VALUES
            ('Servicios', 'gasto', 'lightning-charge'),
            ('Mercado',   'gasto', 'basket'),
            ('Familia',   'gasto', 'people'),
            ('Impuestos', 'gasto', 'file-earmark-text')
        ) AS c(nombre, tipo, icono)
        WHERE NOT EXISTS (
            SELECT 1 FROM categories cat
            WHERE cat.user_id = u.id AND cat.nombre = c.nombre AND cat.tipo = c.tipo
        )
    """)

    ins = []
    for i, (termino, cat, tipo, prio, nota) in enumerate(MODISMOS):
        ins.append(f"('modismo-{i:04d}','{termino}','{cat}','{tipo}',{prio},"
                   + (f"'{nota}'" if nota else "NULL") + ")")
    op.execute(
        "INSERT INTO modismos (id, termino, categoria, tipo, prioridad, nota) VALUES "
        + ",".join(ins)
    )


def downgrade() -> None:
    op.drop_table("modismos")
    op.execute("DELETE FROM payment_methods WHERE nombre IN ('Nequi','Daviplata','Dale','PSE','Nómina')")
    op.execute("DELETE FROM categories WHERE nombre IN ('Servicios','Mercado','Familia','Impuestos')")