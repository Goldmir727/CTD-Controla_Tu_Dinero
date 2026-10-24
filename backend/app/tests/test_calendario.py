"""Calendario del mes: cada movimiento en su día, sin cruzar perfiles.

El calendario es la pantalla donde un error se nota de inmediato (un gasto en el
día equivocado, o el del negocio apareciendo en lo personal), así que se prueba
contra la función del endpoint, que es la que arma la respuesta.
"""
from datetime import date, datetime

import pytest

from app.core.database import SessionLocal
from app.models.finance import Account, Category, Transaction
from app.models.perfil import Perfil
from app.models.user import User


@pytest.fixture()
def escenario():
    db = SessionLocal()
    marca = str(datetime.utcnow().timestamp())
    u = User(nombre="Calendario", correo="cal_%s@example.com" % marca,
             password_hash="x", moneda="COP", plan="pro")
    db.add(u); db.commit(); db.refresh(u)
    personal = Perfil(user_id=u.id, nombre="Personal", tipo="personal", principal=True)
    negocio = Perfil(user_id=u.id, nombre="Negocio", tipo="negocio", principal=False)
    db.add_all([personal, negocio]); db.commit()
    db.refresh(personal); db.refresh(negocio)

    comida = Category(user_id=u.id, perfil_id=personal.id, nombre="Comida", tipo="gasto")
    salario = Category(user_id=u.id, perfil_id=personal.id, nombre="Salario", tipo="ingreso")
    cta = Account(user_id=u.id, perfil_id=personal.id, nombre="Nequi", tipo="otro", saldo_inicial=0)
    cta_neg = Account(user_id=u.id, perfil_id=negocio.id, nombre="Banco", tipo="banco", saldo_inicial=0)
    db.add_all([comida, salario, cta, cta_neg]); db.commit()
    for c in (comida, salario, cta, cta_neg):
        db.refresh(c)

    db.add_all([
        Transaction(user_id=u.id, perfil_id=personal.id, cuenta_id=cta.id,
                    categoria_id=salario.id, tipo="ingreso", monto=1000000,
                    fecha=date(2026, 10, 1), descripcion="Salario"),
        Transaction(user_id=u.id, perfil_id=personal.id, cuenta_id=cta.id,
                    categoria_id=comida.id, tipo="gasto", monto=18000,
                    fecha=date(2026, 10, 8), descripcion="Corrientazo"),
        Transaction(user_id=u.id, perfil_id=personal.id, cuenta_id=cta.id,
                    categoria_id=comida.id, tipo="gasto", monto=4000,
                    fecha=date(2026, 10, 8), descripcion="Café"),
        # Mes distinto: no puede aparecer en el calendario de octubre.
        Transaction(user_id=u.id, perfil_id=personal.id, cuenta_id=cta.id,
                    categoria_id=comida.id, tipo="gasto", monto=22000,
                    fecha=date(2026, 9, 28), descripcion="Mercado"),
        # Otro perfil: tampoco.
        Transaction(user_id=u.id, perfil_id=negocio.id, cuenta_id=cta_neg.id,
                    categoria_id=None, tipo="gasto", monto=300000,
                    fecha=date(2026, 10, 8), descripcion="Proveedor"),
    ])
    db.commit()
    yield db, u, personal, negocio
    for model in (Transaction, Category, Account):
        db.query(model).filter_by(user_id=u.id).delete()
    db.query(Perfil).filter_by(user_id=u.id).delete()
    db.delete(u); db.commit(); db.close()


def test_el_mes_se_agrupa_por_dia_y_los_vacios_siguen_ahi(escenario):
    from app.api.v1.calendario import calendario

    db, u, p, _ = escenario
    r = calendario(mes="2026-10", db=db, user=u, perfil=p)
    assert r["ultimo_dia"] == 31
    assert len(r["dias"]) == 31, "el calendario necesita todos los días para dibujar la cuadrícula"
    assert r["inicio_semana"] == 3, "el 1 de octubre de 2026 cae jueves (0 = lunes)"
    con_mov = [d["dia"] for d in r["dias"] if d["movimientos"]]
    assert con_mov == [1, 8]
    dia8 = r["dias"][7]
    assert dia8["gastos"] == 22000
    assert dia8["balance"] == -22000
    assert [m["descripcion"] for m in dia8["movimientos"]] == ["Corrientazo", "Café"]
    assert dia8["movimientos"][0]["categoria"] == "Comida"
    assert r["totales"] == {"ingresos": 1000000.0, "gastos": 22000.0}
    assert r["dias_con_movimiento"] == 2


def test_el_calendario_no_mezcla_perfiles_ni_meses(escenario):
    from app.api.v1.calendario import calendario

    db, u, p, negocio = escenario
    personal = calendario(mes="2026-10", db=db, user=u, perfil=p)
    dinero_negocio = [m for d in personal["dias"] for m in d["movimientos"]
                      if m["descripcion"] == "Proveedor"]
    assert dinero_negocio == [], "el gasto del negocio no puede salir en lo personal"
    septiembre = [m for d in personal["dias"] for m in d["movimientos"]
                  if m["descripcion"] == "Mercado"]
    assert septiembre == [], "el mercado de septiembre no es de octubre"

    # Y visto desde el negocio, solo está lo del negocio.
    del_negocio = calendario(mes="2026-10", db=db, user=u, perfil=negocio)
    assert del_negocio["totales"] == {"ingresos": 0.0, "gastos": 300000.0}
