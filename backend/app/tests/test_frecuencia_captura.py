"""Captura de fijos CON frecuencia: "me pagan un millón y medio cada quincena".

El bug que esto cubre: la frase se proponia bien (ingreso, 1.500.000, fijo)
pero al confirmar el fijo nacia mensual SIEMPRE, con el dia de hoy AmEN que el
motor lo contaba una vez al mes. Y el monto hablado sin cifras ("un millon y
medio") se marco dudoso porque las reglas no lo veian.
"""
from datetime import date, datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.models.captura import Captura
from app.models.finance import Account, Category, Transaction
from app.models.goals import Recurring
from app.models.perfil import Perfil
from app.models.user import User
from app.services import colombia as co
from app.services import captura_confirmar as capx


FRASE = "me pagan un millón y medio cada quincena"


# ---------- Lo que entienden las reglas deterministas ----------

def test_el_monto_hablado_sin_cifras_se_entiende():
    """\"un millón y medio\" tiene que salir 1.500.000, no quedar dudoso."""
    montos = [m[0] for m in co.montos_en_texto(FRASE)]
    assert 1500000 in montos, montos


def test_medio_millon_como_se_dice():
    assert [m[0] for m in co.montos_en_texto("me transfirieron medio millón")] == [500000]


def test_me_pagan_es_ingreso_no_gasto():
    """\"me pagan\" (presente) no estaba en la lista: la frase era ni ingreso ni gasto."""
    assert co.tipo_por_texto(FRASE) == "ingreso"


def test_cada_quincena_es_quincenal():
    assert co.frecuencia_por_texto(FRASE) == "quincenal"
    assert co.frecuencia_por_texto("pago el internet cada semana") == "semanal"
    assert co.frecuencia_por_texto("pago el arriendo el 5 de cada mes") == "mensual"


def test_una_quincena_pelada_no_inventa_frecuencia():
    """\"me pagaron la quincena\" es un sueldo puntual, no un fijo quincenal."""
    assert co.frecuencia_por_texto("me pagaron la quincena de octubre") is None


def test_cada_domingo_es_semanal_y_dice_que_dia():
    """\"Me pagan 63 mil cada domingo\": semanal, pero ademas el dia exacto.

    Antes quedaba semanal anclado al dia del mes (18), que al mes siguiente ya
    no era domingo.
    """
    frase = "me pagan 63 mil cada domingo"
    assert co.frecuencia_por_texto(frase) == "semanal"
    assert co.dia_semana_por_texto(frase) == 6


def test_un_dia_de_la_semana_suelto_no_es_un_fijo_semanal():
    """\"el lunes pagué el arriendo\" es un movimiento de un dia, no una cuota."""
    assert co.dia_semana_por_texto("el lunes pagué el arriendo") is None
    assert co.frecuencia_por_texto("el lunes pagué el arriendo") is None


def test_todos_los_viernes_tambien_trae_el_dia():
    assert co.dia_semana_por_texto("me pagan todos los viernes") == 4
    assert co.dia_semana_por_texto("pago el gimnasio los sábados") == 5


# ---------- El fijo que se crea al confirmar ----------

@pytest.fixture()
def escenario_captura():
    db = SessionLocal()
    marca = datetime.utcnow().timestamp()
    u = User(nombre="CapFijos", correo="capf_%s@example.com" % marca,
             password_hash="x", moneda="COP")
    db.add(u); db.commit(); db.refresh(u)
    p = Perfil(user_id=u.id, nombre="Personal", tipo="personal", principal=True)
    db.add(p); db.commit(); db.refresh(p)
    cat = Category(user_id=u.id, perfil_id=p.id, nombre="Salario", tipo="ingreso")
    cta = Account(user_id=u.id, perfil_id=p.id, nombre="Nequi", tipo="otro", saldo_inicial=0)
    db.add_all([cat, cta]); db.commit(); db.refresh(cat); db.refresh(cta)
    # Captura vigente: proponer() la crea en la vida real.
    reg = Captura(user_id=u.id, perfil_id=p.id, texto=FRASE, estado="propuesta",
                  propuestos="[]", monto_dudoso=False)
    db.add(reg); db.commit(); db.refresh(reg)
    yield db, u, p, cat, cta, reg
    db.query(Recurring).filter_by(user_id=u.id).delete()
    db.query(Captura).filter_by(user_id=u.id).delete()
    db.query(Transaction).filter_by(user_id=u.id).delete()
    for m in (Account, Category):
        db.query(m).filter_by(user_id=u.id).delete()
    db.query(Perfil).filter_by(user_id=u.id).delete()
    db.delete(u); db.commit(); db.close()


def test_el_fijo_de_la_captura_nace_quincenal(escenario_captura):
    db, u, p, cat, cta, reg = escenario_captura
    mov = [{
        "tipo": "ingreso", "monto": 1500000.0, "categoria_id": cat.id,
        "descripcion": "me pagan un millón y medio cada quincena",
        "metodo_id": None, "cuenta_id": cta.id, "fecha": date.today().isoformat(),
        "fijo": True, "frecuencia": "quincenal", "dia_fijo": 20,
        "recurrente_id": None, "nuevo_fijo": False,
    }]
    r = capx.confirmar_captura(db, u, p, reg.id, mov)
    assert r["errores"] == [], r["errores"]
    fijo = db.query(Recurring).filter_by(user_id=u.id).first()
    assert fijo is not None
    assert fijo.tipo == "ingreso"
    assert float(fijo.monto) == 1500000.0
    assert fijo.frecuencia == "quincenal", "cada quincena se pierde si nace mensual"
    assert fijo.dia == 20


def test_el_fijo_de_cada_domingo_nace_semanal_con_su_dia(escenario_captura):
    """El fijo tiene que caer en domingos de verdad, no en un dia del mes."""
    from app.services import recurrencia as recu

    db, u, p, cat, cta, reg = escenario_captura
    mov = [{
        "tipo": "ingreso", "monto": 63000.0, "categoria_id": cat.id,
        "descripcion": "me pagan 63 mil cada domingo",
        "metodo_id": None, "cuenta_id": cta.id, "fecha": date.today().isoformat(),
        "fijo": True, "frecuencia": "semanal", "dia_fijo": None, "dia_semana": 6,
        "recurrente_id": None, "nuevo_fijo": False,
    }]
    r = capx.confirmar_captura(db, u, p, reg.id, mov)
    assert r["errores"] == [], r["errores"]
    fijo = db.query(Recurring).filter_by(user_id=u.id).first()
    assert fijo.frecuencia == "semanal"
    assert fijo.dia_semana == 6
    fechas = recu.ocurrencias(date.today(), date.today() + timedelta(days=60),
                              fijo.frecuencia, fijo.dia, fijo.dia_semana)
    assert fechas and all(f.weekday() == 6 for f in fechas)


def test_el_dia_de_la_semana_se_ignora_si_el_fijo_es_mensual(escenario_captura):
    """Guardar \"domingo\" en un mensual es un dato que nadie lee."""
    db, u, p, cat, cta, reg = escenario_captura
    mov = [{
        "tipo": "ingreso", "monto": 500000.0, "categoria_id": cat.id,
        "descripcion": "salario", "metodo_id": None, "cuenta_id": cta.id,
        "fecha": date.today().isoformat(), "fijo": True,
        "frecuencia": "mensual", "dia_fijo": 15, "dia_semana": 6,
        "recurrente_id": None, "nuevo_fijo": True,
    }]
    r = capx.confirmar_captura(db, u, p, reg.id, mov)
    assert r["errores"] == [], r["errores"]
    fijo = db.query(Recurring).filter_by(user_id=u.id).first()
    assert fijo.frecuencia == "mensual"
    assert fijo.dia_semana is None


def test_sin_frecuencia_declarada_el_fijo_sigue_siendo_mensual(escenario_captura):
    """Retrocompatibilidad: el boton de siempre (\"esto se repite\") no cambia."""
    db, u, p, cat, cta, reg = escenario_captura
    gasto = Category(user_id=u.id, perfil_id=p.id, nombre="Servicios", tipo="gasto")
    db.add(gasto); db.commit(); db.refresh(gasto)
    mov = [{
        "tipo": "gasto", "monto": 90000.0, "categoria_id": gasto.id,
        "descripcion": "internet", "metodo_id": None, "cuenta_id": cta.id,
        "fecha": date.today().isoformat(),
        "fijo": True, "frecuencia": None, "dia_fijo": None,
        "recurrente_id": None, "nuevo_fijo": False,
    }]
    r = capx.confirmar_captura(db, u, p, reg.id, mov)
    assert r["errores"] == []
    fijo = db.query(Recurring).filter_by(user_id=u.id).first()
    assert fijo.frecuencia == "mensual"
    # Dia de hoy: lo que siempre hizo, primera vez que cae.
    assert fijo.dia == date.today().day
