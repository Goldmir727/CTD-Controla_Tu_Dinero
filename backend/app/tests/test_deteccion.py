"""Deteccion de fijos: cuando el usuario captura algo que ya es un fijo.

Lo que se prueba es la decision de "esto se parece a aquel fijo", porque ahi es
donde una app puede meter la pata de dos formas: no preguntar cuando debe
(duplicando fijos y rompiendo el ratio) o preguntar cuando no debe (molestando
con cada gasto).
"""
from datetime import date, datetime

import pytest

from app.core.database import SessionLocal
from app.models.finance import Account, Category, Transaction
from app.models.goals import Recurring
from app.models.perfil import Perfil
from app.models.user import User
from app.services import deteccion as det


@pytest.fixture()
def con_fijos():
    db = SessionLocal()
    u = User(nombre="Det", correo="det_%s@example.com" % datetime.utcnow().timestamp(),
             password_hash="x", moneda="COP")
    db.add(u); db.commit(); db.refresh(u)
    p = Perfil(user_id=u.id, nombre="Personal", tipo="personal", principal=True)
    negocio = Perfil(user_id=u.id, nombre="Negocio", tipo="negocio", principal=False)
    db.add_all([p, negocio]); db.commit(); db.refresh(p); db.refresh(negocio)
    db.add(Recurring(user_id=u.id, perfil_id=p.id, nombre="Arriendo", tipo="gasto",
                     monto=1200000, dia=5, frecuencia="mensual", activo=True))
    db.commit()
    yield db, u, p, negocio
    for m in (Recurring, Transaction):
        db.query(m).filter_by(user_id=u.id).delete()
    db.query(Category).filter_by(user_id=u.id).delete()
    db.query(Account).filter_by(user_id=u.id).delete()
    db.query(Perfil).filter_by(user_id=u.id).delete()
    db.delete(u); db.commit(); db.close()


# ---- Parecido de nombre: comparar palabras, no letras ----

def test_el_nombre_se_compara_con_palabras_no_con_letras():
    """Comparar caracteres daria parecido entre cosas que no tienen que ver.

    "arriendo" y "salario" comparten cuatro letras: con caracteres se verian
    parecidos. Con palabras, cero, que es lo correcto.
    """
    assert det._parecido_nombre("pagué el arriendo", "Arriendo") > 0.6
    assert det._parecido_nombre("arriendo", "salario") == 0.0
    assert det._parecido_nombre("internet", "salario") == 0.0


def test_los_conectores_no_cuentan_como_similitud():
    """"pago de arriendo" y "Arriendo" son el mismo gasto.

    Las palabras de relleno (de, la, pago, mes) se quitan antes de comparar; si
    contaran, dos frases sobre lo mismo darian parecido bajo.
    """
    assert det._parecido_nombre("pago de arriendo del mes", "Arriendo") > 0.6
    assert det._parecido_nombre("gaste en arriendo", "Arriendo") > 0.6


def test_los_acentos_no_cuentan_como_palabras_distintas():
    assert det._parecido_nombre("café", "Cafe") == 1.0
    assert det._parecido_nombre("arriendo", "ARRIENDO") == 1.0


# ---- Parecido de monto: subir un arriendo no lo vuelve otro fijo ----

def test_el_arriendo_que_subio_un_poco_sigue_siendo_el_mismo():
    """Es el caso real: el arriendo sube 50.000 al año.

    Si eso creara un fijo nuevo, el usuario terminaria con dos y el motor los
    sumaria doble.
    """
    assert det._parecido_monto(1250000, 1200000) > 0.8
    assert det._parecido_monto(1200000, 1200000) == 1.0


def test_un_monto_muy_distinto_no_se_parece():
    assert det._parecido_monto(1200000, 50000) == 0.0


# ---- Detectar sobre la BD ----

def test_detecta_el_arriendo_cuando_el_usuario_lo_nombra(con_fijos):
    db, u, p, negocio = con_fijos
    c = det.detectar(db, u.id, p.id, "pagué el arriendo de octubre", "gasto", 1200000, 5)
    assert len(c) == 1
    assert c[0]["nombre"] == "Arriendo"
    assert c[0]["confianza"] >= det.CONFIANZA_MINIMA


def test_no_detecta_un_gasto_que_no_se_parece(con_fijos):
    """Si pregunta por cada captura, el usuario deja de mirar la pregunta."""
    db, u, p, negocio = con_fijos
    c = det.detectar(db, u.id, p.id, "almuerzo con los amigos", "gasto", 45000, 12)
    assert c == [], f"no debería preguntar por un almuerzo: {c}"


def test_ingreso_nunca_coincide_con_un_gasto_mismo_nombre(con_fijos):
    """"Salario" de ingreso y "Salario" de gasto no son el mismo fijo."""
    db, u, p, negocio = con_fijos
    db.add(Recurring(user_id=u.id, perfil_id=p.id, nombre="Salario", tipo="gasto",
                     monto=100000, dia=1, frecuencia="mensual", activo=True))
    db.commit()
    assert det.detectar(db, u.id, p.id, "salario", "ingreso", 100000, 1) == []


def test_no_busca_fijos_de_otro_perfil(con_fijos):
    db, u, p, negocio = con_fijos
    db.add(Recurring(user_id=u.id, perfil_id=negocio.id, nombre="Nomina", tipo="gasto",
                     monto=2500000, dia=5, frecuencia="mensual", activo=True))
    db.commit()
    assert det.detectar(db, u.id, p.id, "pagué la nómina", "gasto", 2500000, 5) == []


def test_un_fijo_pausado_no_se_pregunta(con_fijos):
    """Pausar es decir "ya no me pregunten por esto"."""
    db, u, p, negocio = con_fijos
    db.query(Recurring).filter_by(user_id=u.id).update({"activo": False})
    db.commit()
    assert det.detectar(db, u.id, p.id, "pagué el arriendo", "gasto", 1200000, 5) == []


def test_el_dia_del_mes_ayuda_a_no_confundir(con_fijos):
    """Dos fijos parecidos en monto pero en dias distintos: el dia los separa."""
    db, u, p, negocio = con_fijos
    db.add(Recurring(user_id=u.id, perfil_id=p.id, nombre="Arriendo", tipo="gasto",
                     monto=1200000, dia=28, frecuencia="mensual", activo=True))
    db.commit()
    c = det.detectar(db, u.id, p.id, "arriendo", "gasto", 1200000, 28)
    assert c and c[0]["dia"] == 28, "debe ganar el que coincide con el dia del movimiento"
    c5 = det.detectar(db, u.id, p.id, "arriendo", "gasto", 1200000, 5)
    assert c5 and c5[0]["dia"] == 5


# ---- Sugerir el fijo que el usuario todavia no declaro ----

def test_sugiere_crear_un_fijo_que_se_repite(con_fijos):
    """Tres meses pagando lo mismo es un fijo que el usuario no declaro."""
    db, u, p, negocio = con_fijos
    cat = Category(user_id=u.id, perfil_id=p.id, nombre="Servicios", tipo="gasto")
    cta = Account(user_id=u.id, perfil_id=p.id, nombre="Nequi", tipo="otro", saldo_inicial=0)
    db.add_all([cat, cta]); db.commit(); db.refresh(cat); db.refresh(cta)
    for f in (date(2026, 7, 8), date(2026, 8, 8), date(2026, 9, 8)):
        db.add(Transaction(user_id=u.id, perfil_id=p.id, cuenta_id=cta.id,
                           categoria_id=cat.id, tipo="gasto", monto=95000,
                           descripcion="pago internet", fecha=f))
    db.commit()
    s = det.sugerir_fijos(db, u.id, p.id)
    assert any("internet" in x["nombre"].lower() for x in s), f"no lo sugirio: {s}"
    assert s[0]["veces_visto"] == 3
    assert s[0]["dia"] == 8


def test_no_sugiere_una_ocurrencia_suelta(con_fijos):
    """Un gasto unico no es un fijo. Si se sugiere, la pantalla se llena de ruido."""
    db, u, p, negocio = con_fijos
    cat = Category(user_id=u.id, perfil_id=p.id, nombre="Ocio", tipo="gasto")
    cta = Account(user_id=u.id, perfil_id=p.id, nombre="Nequi", tipo="otro", saldo_inicial=0)
    db.add_all([cat, cta]); db.commit(); db.refresh(cat); db.refresh(cta)
    db.add(Transaction(user_id=u.id, perfil_id=p.id, cuenta_id=cta.id, categoria_id=cat.id,
                       tipo="gasto", monto=90000, descripcion="concierto",
                       fecha=date(2026, 9, 8)))
    db.commit()
    assert det.sugerir_fijos(db, u.id, p.id) == []


def test_no_sugiere_lo_que_ya_esta_declarado(con_fijos):
    """Sugerir un fijo que el usuario ya declaro es ruido puro."""
    db, u, p, negocio = con_fijos
    cat = Category(user_id=u.id, perfil_id=p.id, nombre="Vivienda", tipo="gasto")
    cta = Account(user_id=u.id, perfil_id=p.id, nombre="Nequi", tipo="otro", saldo_inicial=0)
    db.add_all([cat, cta]); db.commit(); db.refresh(cat); db.refresh(cta)
    for f in (date(2026, 7, 5), date(2026, 8, 5), date(2026, 9, 5)):
        db.add(Transaction(user_id=u.id, perfil_id=p.id, cuenta_id=cta.id,
                           categoria_id=cat.id, tipo="gasto", monto=1200000,
                           descripcion="Arriendo", fecha=f))
    db.commit()
    nombres = [x["nombre"].lower() for x in det.sugerir_fijos(db, u.id, p.id)]
    assert "arriendo" not in nombres, f"sugirio un fijo ya declarado: {nombres}"