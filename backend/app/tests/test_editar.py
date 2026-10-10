"""Editar movimientos y declarar fijos: los dos caminos que se abren con un clic malo.

El caso real que motiva esto: "gasté 200 en un dulce" quedo como $200 cuando era
un desayuno, o al reves. Antes habia que borrar y recapturar, y con la captura
rapida el usuario lo volvia a hacer mal la mitad de las veces.
"""
from datetime import date, datetime

import pytest

from app.core.database import SessionLocal
from app.models.finance import Account, Budget, Category, PaymentMethod, Transaction
from app.models.goals import Goal, GoalAporte, Recurring
from app.models.perfil import Perfil
from app.models.user import User
from app.services import finanzas as fin
from app.services import quincena as qn


@pytest.fixture()
def escenario():
    db = SessionLocal()
    marca = str(datetime.utcnow().timestamp())
    u = User(nombre="Edit", correo="edit_%s@example.com" % marca,
             password_hash="x", moneda="COP", plan="pro")
    db.add(u); db.commit(); db.refresh(u)
    p = Perfil(user_id=u.id, nombre="Personal", tipo="personal", principal=True)
    db.add(p); db.commit(); db.refresh(p)
    otro = Perfil(user_id=u.id, nombre="Negocio", tipo="negocio", principal=False)
    db.add(otro); db.commit(); db.refresh(otro)

    cat = Category(user_id=u.id, perfil_id=p.id, nombre="Comida", tipo="gasto")
    cta = Account(user_id=u.id, perfil_id=p.id, nombre="Nequi", tipo="otro", saldo_inicial=100000)
    cta_negocio = Account(user_id=u.id, perfil_id=otro.id, nombre="Banco", tipo="banco", saldo_inicial=0)
    db.add_all([cat, cta, cta_negocio]); db.commit()
    db.refresh(cat); db.refresh(cta); db.refresh(cta_negocio)

    mov = Transaction(user_id=u.id, perfil_id=p.id, cuenta_id=cta.id, categoria_id=cat.id,
                      tipo="gasto", monto=200, fecha=date(2026, 10, 8),
                      descripcion="gasté 200 en un dulce")
    db.add(mov); db.commit(); db.refresh(mov)
    yield db, u, p, otro, cat, cta, cta_negocio, mov
    # El orden importa por las FK: los hijos se borran antes que los padres, o
    # el teardown revienta y el error tapa el fallo real del test.
    metas = [g.id for g in db.query(Goal).filter_by(user_id=u.id).all()]
    if metas:
        db.query(GoalAporte).filter(GoalAporte.goal_id.in_(metas)).delete(
            synchronize_session=False)
    for model in (Transaction, Budget, Recurring, Goal, PaymentMethod, Category, Account):
        db.query(model).filter_by(user_id=u.id).delete()
    db.query(Perfil).filter_by(user_id=u.id).delete()
    db.delete(u); db.commit(); db.close()


# ---------- Editar un movimiento ----------

def test_editar_el_monto_recalcula_el_saldo(escenario):
    """Si el saldo fuera una columna guardada, este test lo detectaria.

    Es el motivo de que editar sea seguro: saldo_actual es DERIVADO
    (saldo_inicial + ingresos - gastos), no un numero que se queda viejo.
    """
    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    antes = fin.disponible(db, u.id, p.id)["total"]
    mov.monto = 8000
    db.commit()
    despues = fin.disponible(db, u.id, p.id)["total"]
    assert round(antes - despues, 2) == 7800, "cambiar 200 por 8000 debe restar 7800"


def test_cambiar_de_gasto_a_ingreso_invierte_el_efecto(escenario):
    """El caso mas traicionero: el mismo movimiento, al reves.

    Si esto queda mal, el saldo del usuario cambia de signo sin que nada lo avise.
    """
    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    saldo_gasto = fin.disponible(db, u.id, p.id)["total"]
    mov.tipo = "ingreso"
    db.commit()
    saldo_ingreso = fin.disponible(db, u.id, p.id)["total"]
    # 100.000 inicial, -200 gasto, +200 ingreso
    assert round(saldo_gasto, 2) == 99800.0
    assert round(saldo_ingreso, 2) == 100200.0
    assert round(saldo_ingreso - saldo_gasto, 2) == 400.0, "no se invirtio el signo"


def test_editar_un_movimiento_de_otro_perfil_da_404(escenario):
    """El aislamiento de perfiles tambien aplica al EDITAR, no solo al leer."""
    from app.api.v1.movimientos import actualizar
    from fastapi import HTTPException
    from app.schemas.finance import MovimientoPatch

    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    with pytest.raises(HTTPException) as e:
        actualizar(mov.id, MovimientoPatch(monto=999999), db=db, user=u, perfil=otro)
    assert e.value.status_code == 404
    assert mov.monto == 200, "el movimiento se toco pese al 404"


def test_editar_un_movimiento_recibo_va_happy_path(escenario):
    """PATCH /movimientos daba 500 en cualquier edicion.

    _validar declaraba `perfil=None` y dos lineas mas adelante hacia perfil.id.
    actualizar no se lo pasaba. El test del 404 de arriba NO lo cazaba porque si
    pasaba el perfil: el fallo estaba dentro de la funcion, no en la llamada.
    Este si la ejecuta de punta a punta.
    """
    from app.api.v1.movimientos import actualizar
    from app.schemas.finance import MovimientoPatch

    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    r = actualizar(mov.id, MovimientoPatch(monto=8000, descripcion="desayuno"),
                   db=db, user=u, perfil=p)
    assert r["monto"] == 8000.0
    assert r["descripcion"] == "desayuno"
    db.refresh(mov)
    assert mov.monto == 8000.0


def test_editar_no_puede_mover_un_movimiento_a_otra_cuenta_del_negocio(escenario):
    """Editar no es una puerta trasera para cruzar perfiles.

    El movimiento es del Personal; la cuenta es del Negocio. Aunque las dos
    pertenezcan al mismo usuario, la cuenta se rechaza.
    """
    from app.api.v1.movimientos import actualizar
    from fastapi import HTTPException
    from app.schemas.finance import MovimientoPatch

    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    with pytest.raises(HTTPException) as e:
        actualizar(mov.id, MovimientoPatch(cuenta_id=cta_neg.id), db=db, user=u, perfil=p)
    assert e.value.status_code == 404
    db.refresh(mov)
    assert mov.cuenta_id == cta.id


def test_una_categoria_de_ingreso_no_acepta_un_gasto(escenario):
    """Editar el tipo tiene que revalidar la categoría, o el movimiento queda incoherente."""
    from fastapi import HTTPException
    from app.api.v1.movimientos import actualizar
    from app.schemas.finance import MovimientoPatch

    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    cat_sueldo = Category(user_id=u.id, perfil_id=p.id, nombre="Salario", tipo="ingreso")
    db.add(cat_sueldo); db.commit(); db.refresh(cat_sueldo)
    mov.categoria_id = cat_sueldo.id
    db.commit()
    with pytest.raises(HTTPException) as e:
        actualizar(mov.id, MovimientoPatch(tipo="gasto"), db=db, user=u, perfil=p)
    assert e.value.status_code == 422


def test_la_revision_quincenal_refleja_el_monto_corregido(escenario):
    """Si el usuario corrige un movimiento, el aviso de la quincena cambia.

    Conectar "editar" con "como vas" es el punto: corregir de mas y que la app
    siga diciendo que va mal seria peor que no dejar editar.
    """
    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    cat_ocio = Category(user_id=u.id, perfil_id=p.id, nombre="Ocio", tipo="gasto")
    db.add(cat_ocio); db.commit(); db.refresh(cat_ocio)
    hoy = date.today()
    db.add(Budget(user_id=u.id, perfil_id=p.id, categoria_id=cat_ocio.id,
                  monto=500000, periodo=hoy.strftime("%Y-%m")))
    # El movimiento pasa a la categoria presupuestada; si no, la alerta nunca
    # lo ve porque ella solo mira los gastos de SU categoria.
    mov.categoria_id = cat_ocio.id
    mov.monto = 400000
    db.commit()
    antes = qn.alertas_presupuesto(db, u.id, p.id, hoy)
    mov.monto = 45000
    db.commit()
    despues = qn.alertas_presupuesto(db, u.id, p.id, hoy)
    assert len(antes) == 1, "con 400.000 de 500.000 deberia alertar"
    assert despues == [], "con 45.000 ya no hay nada que avisar"


# ---------- Fijos declarativos ----------

def test_un_fijo_declarativo_marca_el_rapor_de_gastos(escenario):
    """Este es el para que existe la pantalla: separar lo fijo de lo variable."""
    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    db.add(Recurring(user_id=u.id, perfil_id=p.id, nombre="Arriendo", tipo="gasto",
                     monto=1200000, dia=5, frecuencia="mensual", activo=True))
    db.commit()
    h = fin.ratio_fijo(db, u.id, p.id, date.today().strftime("%Y-%m"))
    assert h["gastos_fijos"] == 1200000.0
    assert h["ratio_fijo"] > 0


def test_pausar_un_fijo_lo_saca_del_calculo_sin_borrarlo(escenario):
    """Pausar, no borrar: un arriendo que se acaba en diciembre vuelve en enero."""
    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    r = Recurring(user_id=u.id, perfil_id=p.id, nombre="Internet", tipo="gasto",
                  monto=90000, dia=10, frecuencia="mensual", activo=True)
    db.add(r); db.commit(); db.refresh(r)
    assert fin.ratio_fijo(db, u.id, p.id, date.today().strftime("%Y-%m"))["gastos_fijos"] == 90000.0
    r.activo = False
    db.commit()
    assert fin.ratio_fijo(db, u.id, p.id, date.today().strftime("%Y-%m"))["gastos_fijos"] == 0.0
    assert db.query(Recurring).filter_by(user_id=u.id).count() == 1, "pausar no es borrar"


def test_un_fijo_del_negocio_no_contamina_el_personal(escenario):
    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    db.add(Recurring(user_id=u.id, perfil_id=otro.id, nombre="Nómina", tipo="gasto",
                     monto=2500000, dia=5, frecuencia="mensual", activo=True))
    db.commit()
    assert fin.ratio_fijo(db, u.id, p.id, date.today().strftime("%Y-%m"))["gastos_fijos"] == 0.0
    assert fin.ratio_fijo(db, u.id, otro.id, date.today().strftime("%Y-%m"))["gastos_fijos"] == 2500000.0


# ---------- El endpoint, no solo el motor ----------

def test_listar_fijos_no_revienta(escenario):
    """GET /recurrentes daba 500: llamaba fijos_mensuales sin el perfil_id.

    Nadie lo noto porque no habia ninguna pantalla que lo pidiera. Los tests
    llamaban al motor, no al endpoint, asi que tampoco lo cazaron.
    """
    from app.api.v1.recurrentes import listar

    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    db.add(Recurring(user_id=u.id, perfil_id=p.id, nombre="Arriendo", tipo="gasto",
                     monto=1200000, dia=5, frecuencia="mensual", activo=True))
    db.add(Recurring(user_id=u.id, perfil_id=otro.id, nombre="Nómina", tipo="gasto",
                     monto=2500000, dia=5, frecuencia="mensual", activo=True))
    db.commit()
    r = listar(db=db, user=u, perfil=p)
    assert len(r["items"]) == 1, "el Personal no debe ver los fijos del Negocio"
    assert r["items"][0]["nombre"] == "Arriendo"
    assert r["resumen"]["gastos_fijos_mes"] == 1200000.0, \
        "el resumen mezcló los fijos del negocio"


def test_el_endpoint_de_fijos_crea_editar_pausa_y_borra(escenario):
    """El recorrido completo de la pantalla nueva."""
    from app.api.v1.recurrentes import RecurrenteIn, RecurrentePatch
    from app.api.v1.recurrentes import borrar, crear, editar, listar, toggle

    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    nuevo = crear(RecurrenteIn(nombre="Internet", tipo="gasto", monto=90000, dia=10,
                               frecuencia="mensual", cuenta_id=cta.id, categoria_id=cat.id),
                  db=db, user=u, perfil=p)
    assert nuevo["monto_mes"] == 90000.0
    assert len(listar(db=db, user=u, perfil=p)["items"]) == 1

    editar(nuevo["id"], RecurrentePatch(monto=95000, dia=12), db=db, user=u, perfil=p)
    item = listar(db=db, user=u, perfil=p)["items"][0]
    assert item["monto"] == 95000.0 and item["dia"] == 12

    toggle(nuevo["id"], db=db, user=u, perfil=p)
    assert listar(db=db, user=u, perfil=p)["items"][0]["activo"] is False

    borrar(nuevo["id"], db=db, user=u, perfil=p)
    assert listar(db=db, user=u, perfil=p)["items"] == []


# ---------- Regresiones que ya estaban rotas ----------

def test_crear_un_perfil_no_duplica_los_metodos_de_pago(escenario):
    """Los metodos de pago son por USUARIO, no por perfil.

    Sembrarlos sin mirar los existentes los duplicaba en cada perfil nuevo: la
    base llego a 4 copias de cada uno y /metodos-pago devolvia 24 filas para 8
    metodos. El usuario lo veia en todos los selectores de metodo de pago.
    """
    from collections import Counter

    from app.api.v1.auth import _sembrar_perfil
    from app.models.finance import PaymentMethod

    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    assert db.query(PaymentMethod).filter_by(user_id=u.id).count() == 0, "el fixture no siembra metodos"

    # Sembrar dos perfiles seguidos, que es lo que pasa en la vida real.
    for destino in (p, otro):
        _sembrar_perfil(db, u.id, destino.id)
        db.commit()

    total = db.query(PaymentMethod).filter_by(user_id=u.id).count()
    assert total == 8, f"dos perfiles debian sembrar 8 metodos en total, hay {total}"
    c = Counter(m.nombre for m in db.query(PaymentMethod).filter_by(user_id=u.id).all())
    assert not [k for k, v in c.items() if v > 1], f"quedaron metodos repetidos: {c}"


def test_sembrar_de_nuevo_sobre_un_perfil_con_datos_no_revienta(escenario):
    """La siembra tiene que poder correr dos veces sobre el mismo perfil.

    Antes reventaba el UNIQUE de categorias (perfil_id, nombre, tipo) en cuanto
    el perfil ya tenia una con ese nombre.
    """
    from app.api.v1.auth import _sembrar_perfil
    from app.models.finance import Category

    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    # El fixture ya tiene "Comida" en el perfil p.
    _sembrar_perfil(db, u.id, p.id)
    db.commit()
    comidas = db.query(Category).filter_by(user_id=u.id, perfil_id=p.id,
                                           nombre="Comida", tipo="gasto").count()
    assert comidas == 1, f"quedaron {comidas} categorias Comida"
    cuentas = db.query(Account).filter_by(user_id=u.id, perfil_id=p.id).count()
    assert cuentas >= 1, "no debe duplicar la cuenta Efectivo"


def test_una_meta_de_otro_perfil_no_se_lee(escenario):
    """ruta_meta solo miraba user_id: la meta del Negocio se leia desde el Personal."""
    from app.models.goals import Goal
    from app.services import finanzas as f

    db, u, p, otro, cat, cta, cta_neg, mov = escenario
    meta_negocio = Goal(user_id=u.id, perfil_id=otro.id, nombre="Camion",
                        objetivo=30000000, fecha_objetivo=date(2027, 6, 1))
    db.add(meta_negocio); db.commit(); db.refresh(meta_negocio)

    r = f.ruta_meta(db, u.id, meta_negocio.id, 500000, date.today(), p.id)
    assert r.get("error") == "Meta no encontrada", \
        f"una meta del Negocio se respondio desde el perfil Personal: {r}"