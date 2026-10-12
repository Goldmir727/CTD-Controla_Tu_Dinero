"""Tests del periodo de revision: mes o quincena, segon elija el usuario.

Por que existen aparte de los de quincena: el default cambio a MES. Antes
`revision` cortaba por quincena siempre, sin mirar ni al pais ni al usuario, y
`usa_quincena` solo cambiaba el texto del tour. Un usuario de Estados Unidos
veia "primera quincena, dia 12 de 15" sobre una matematica que no era suya.

Aqui se comprueba lo que NO se puede comprobar a ojo: que el corte, los dias y el
recuento de fijos cambien de verdad. Si solo se cambiaran las etiquetas, estos
tests darian verde mientras la app sigue partiendo el dia 15.
"""
from datetime import date

import pytest

from app.services import periodo as per


# ---------- el corte del periodo ----------

def test_el_mes_va_de_primer_dia_a_ultimo():
    p = per.periodo(date(2026, 10, 12), usa_quincena=False)
    assert p["inicio"] == "2026-10-01"
    assert p["fin"] == "2026-10-31"
    assert p["dias_totales"] == 31
    assert p["dias_transcurridos"] == 12
    assert p["dias_restantes"] == 19
    assert p["usa_quincena"] is False


def test_la_quincena_sigue_partiendo_el_15():
    p = per.periodo(date(2026, 10, 12), usa_quincena=True)
    assert p["inicio"] == "2026-10-01"
    assert p["fin"] == "2026-10-15"
    assert p["dias_totales"] == 15
    assert p["dias_transcurridos"] == 12
    assert p["usa_quincena"] is True


def test_febrero_no_revienta_ni_en_mes():
    """El mismo ValueError del dia 30 de febrero, ahora en el camino mensual."""
    p = per.periodo(date(2026, 2, 20), usa_quincena=False)
    assert p["fin"] == "2026-02-28"
    assert p["dias_totales"] == 28


def test_bisiesto_respeta_el_29():
    p = per.periodo(date(2028, 2, 10), usa_quincena=False)
    assert p["fin"] == "2028-02-29"
    assert p["dias_totales"] == 29


def test_etiquetas_legibles_de_cada_periodo():
    assert per.etiqueta_periodo("2026-10", False) == "octubre de 2026"
    assert per.etiqueta_periodo("2026-10-Q1", True) == "primera quincena de octubre"
    assert per.etiqueta_periodo("basura", False) == "basura"


def test_el_periodo_anterior_es_el_mismo_tipo():
    """Comparar un mes contra una quincena daria un numero cierto sobre una
    comparacion falsa."""
    mes = per.periodo(date(2026, 10, 12), usa_quincena=False)
    assert per.periodo_anterior(mes, False)["etiqueta"] == "2026-09"
    # Cruzar el 31 de diciembre no puede devolver "2026-00".
    dic = per.periodo(date(2026, 12, 5), usa_quincena=False)
    assert per.periodo_anterior(dic, False)["etiqueta"] == "2026-11"

    q = per.periodo(date(2026, 10, 20), usa_quincena=True)
    # La segunda quincena se compara con la segunda, no con la primera.
    assert per.periodo_anterior(q, True)["etiqueta"] == "2026-09-Q2"


# ---------- el motor completo ----------

@pytest.fixture()
def escenario_mensual():
    from datetime import datetime

    from app.core.database import SessionLocal
    from app.models.finance import Account, Category, Transaction
    from app.models.goals import Recurring
    from app.models.perfil import Perfil
    from app.models.user import User

    db = SessionLocal()
    marca = str(datetime.utcnow().timestamp())
    u = User(nombre="Mensual", correo="mensual_%s@example.com" % marca,
             password_hash="x", moneda="COP", plan="pro")
    db.add(u)
    db.commit()
    db.refresh(u)
    p = Perfil(user_id=u.id, nombre="Personal", tipo="personal", principal=True)
    db.add(p)
    db.commit()
    db.refresh(p)

    hoy = date.today()
    cat = Category(user_id=u.id, perfil_id=p.id, nombre="Comida", tipo="gasto")
    db.add(cat)
    cuenta = Account(user_id=u.id, perfil_id=p.id, nombre="Banco", tipo="banco",
                     saldo_inicial=0)
    db.add(cuenta)
    db.commit()
    db.refresh(cat)
    db.refresh(cuenta)
    db.add(Transaction(user_id=u.id, perfil_id=p.id, tipo="gasto", monto=100000,
                       fecha=hoy, descripcion="Compra", categoria_id=cat.id,
                       cuenta_id=cuenta.id))
    db.commit()
    yield db, u, p, cat, hoy
    db.query(Transaction).filter_by(user_id=u.id).delete()
    db.query(Recurring).filter_by(user_id=u.id).delete()
    db.query(Category).filter_by(user_id=u.id).delete()
    db.query(Account).filter_by(user_id=u.id).delete()
    db.query(Perfil).filter_by(user_id=u.id).delete()
    db.query(User).filter_by(id=u.id).delete()
    db.commit()
    db.close()


def test_por_defecto_la_revision_usa_el_mes(escenario_mensual):
    """El default es mes. Si esto cambia, la app vuelve a encerrarse."""
    from app.services import quincena as qn

    db, u, p, cat, hoy = escenario_mensual
    r = qn.revision(db, u.id, p.id, hoy, usa_quincena=False)
    assert r["usa_quincena"] is False
    assert r["quincena"]["fin"] == f"{hoy.year:04d}-{hoy.month:02d}-{per.mes(hoy)['fin'][-2:]}"
    assert r["etiqueta_legible"].endswith("de %d" % hoy.year)


def test_el_mes_cuenta_un_fijo_del_dia_20_que_la_quincena_no_ve(escenario_mensual):
    """Este es el teste que demuestra que el motor cambio de verdad.

    Un arriendo del dia 20 en la PRIMERA quincena no vence todavia (quedan dias),
    pero en el mes completo si cae. Si el motor fuera el mismo con otra etiqueta,
    el fijo no apareceria y el usuario veria "fijos que vencen: 0" el dia 20.
    """
    from app.services import quincena as qn
    from app.models.goals import Recurring

    db, u, p, cat, hoy = escenario_mensual
    db.add(Recurring(user_id=u.id, perfil_id=p.id, nombre="Arriendo", tipo="gasto",
                     monto=1200000, dia=20, frecuencia="mensual", activo=True))
    db.commit()
    try:
        dia3 = date(hoy.year, hoy.month, 3)
        r_quincena = qn.revision(db, u.id, p.id, dia3, usa_quincena=True)
        r_mes = qn.revision(db, u.id, p.id, dia3, usa_quincena=False)

        assert r_quincena["fijos"]["total"] == 0, "en la primera quincena no vence aun"
        assert r_mes["fijos"]["total"] == 1200000, "en el mes completo si vence"
    finally:
        db.query(Recurring).filter_by(user_id=u.id).delete()
        db.commit()


def test_el_mensaje_no_habla_de_quincena_a_quien_razona_por_mes(escenario_mensual):
    """El texto era la parte visible del problema: decia 'esta quincena' a todos."""
    from app.services import quincena as qn

    db, u, p, cat, hoy = escenario_mensual
    r = qn.revision(db, u.id, p.id, hoy, usa_quincena=False)
    assert "quincena" not in r["mensaje"].lower()
    assert "mes" in r["mensaje"].lower()


def test_el_mensaje_de_quincena_sigue_diciendola(escenario_mensual):
    from app.services import quincena as qn

    db, u, p, cat, hoy = escenario_mensual
    r = qn.revision(db, u.id, p.id, date(hoy.year, hoy.month, 3), usa_quincena=True)
    assert "quincena" in r["mensaje"].lower()