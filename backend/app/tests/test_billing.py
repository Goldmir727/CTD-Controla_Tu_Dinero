"""Tests del cobro con Wompi.

El foco es la FIRMA. El resto del flujo se puede reponer activating PRO a mano en
la base; una firma mal implementada no tiene arreglo: o rechaza pagos legitimos
(la gente paga y no entra) o acepta los forjados (cualquiera se hace PRO).

Cada test arma un evento con la MISMA regla que usa `wompi.checksum_esperado` y
luego lo altera. Si la regla estuviera mal, los dos usarian el mismo error y el
test pasaria igual, asi que hay un test que fija el valor a mano contra el
ejemplo de la documentacion.
"""
import hashlib
import uuid
from datetime import date, datetime

import pytest

from app.services import wompi

SECRETO = "events_secreto_de_prueba"


def _evento(status="APPROVED", referencia="ctd-abc123", monto=1500000,
            properties=None, ts=1700000000, secret=SECRETO, extra=None):
    props = properties or ["transaction_id", "status", "reference", "amount_in_cents"]
    data = {
        "transaction_id": "tx-999",
        "status": status,
        "reference": referencia,
        "amount_in_cents": monto,
        "customer_email": "juan@example.com",
    }
    data.update(extra or {})
    evento = {
        "event": "transaction.updated",
        "data": data,
        "environment": "prod",
        "signature": {"properties": props, "timestamp": ts, "checksum": ""},
    }
    if secret and all(p in data for p in props):
        crudo = "".join(str(data[p]) for p in props) + str(ts) + secret
        evento["signature"]["checksum"] = hashlib.sha256(crudo.encode()).hexdigest()
    return evento


# ---------- la regla de la firma ----------


def test_firma_correcta_se_acepta():
    assert wompi.firma_valida(_evento(), SECRETO) is True


def test_firma_con_secreto_distinto_se_rechaza():
    """Este es EL test de seguridad: si otro secreto no falla, cualquiera
    podriaingerse PRO con un evento manufactured."""
    assert wompi.firma_valida(_evento(), "otro_secreto") is False


def test_firma_manipulada_se_rechaza():
    """Alguien sube el monto a 0 y reusa el evento."""
    e = _evento()
    e["data"]["amount_in_cents"] = 0
    assert wompi.firma_valida(e, SECRETO) is False


def test_el_header_tambien_sirve():
    e = _evento()
    chk = e["signature"]["checksum"]
    assert wompi.firma_valida(e, SECRETO, header_checksum=chk) is True


def test_evento_sin_firma_no_pasa():
    assert wompi.firma_valida({"event": "transaction.updated", "data": {}}, SECRETO) is False


def test_evento_sin_secreto_configurado_no_pasa():
    """Sin secreto no hay nada que verificar, asi que no se acepta nada."""
    assert wompi.firma_valida(_evento(), "") is False


def test_campo_declarado_pero_ausente_no_se_inventa():
    """La lista de propiedades viene del evento; si falta un valor no se puede
    reproducir el hash, y adivinar seria justo el fallo que se quiere evitar."""
    e = _evento(properties=["transaction_id", "campo_que_no_existe"])
    assert wompi.firma_valida(e, SECRETO) is False


def test_la_lista_de_propiedades_se_lee_del_evento():
    """Wompi puede agregar un campo a la firma. Si estuviera fija en el codigo,
    todos los eventos dejarian de validar."""
    e = _evento(properties=["transaction_id", "status", "reference",
                            "amount_in_cents", "environment"],
                extra={"environment": "prod"})
    assert wompi.firma_valida(e, SECRETO) is True


def test_valor_fijo_contra_la_documentacion():
    """Caso congelado contra el ejemplo de la documentacion de Wompi.

    Si esto cambia, el algoritmo cambio y hay que volver a leer la documentacion
    ANTES de tocar nada:aceptar de mas regala PRO, rechazar de mas hace que la
    gente pague y no entre.
    """
    e = {
        "event": "transaction.updated",
        "data": {"transaction_id": "1234", "status": "APPROVED",
                 "reference": "49201", "amount_in_cents": 4490000},
        "signature": {"properties": ["transaction_id", "status", "reference",
                                     "amount_in_cents"],
                      "timestamp": 1610641025, "checksum": ""},
    }
    crudo = "1234" + "APPROVED" + "49201" + "4490000" + "1610641025" + "secreto"
    e["signature"]["checksum"] = hashlib.sha256(crudo.encode()).hexdigest()
    assert wompi.firma_valida(e, "secreto") is True


# ---------- lectura de eventos ----------


def test_solo_approved_activate():
    assert wompi.es_aprobada(_evento(status="APPROVED")) is True
    assert wompi.es_aprobada(_evento(status="DECLINED")) is False
    assert wompi.es_aprobada(_evento(status="ERROR")) is False


def test_referencia_llega_limpia():
    assert wompi.referencia({"reference": "  ctd-xyz  "}) == "ctd-xyz"
    assert wompi.referencia({}) == ""


def test_referencias_no_se_repiten():
    """Dos cobros con la misma referencia se tranzan juntos en Wompi."""
    refs = {wompi.referencia_nueva("ctd") for _ in range(200)}
    assert len(refs) == 200


# ---------- flujo completo ----------


@pytest.fixture()
def entorno():
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.billing import Suscripcion
    from app.models.perfil import Perfil
    from app.models.user import User
    from fastapi.testclient import TestClient

    from app.core import config as config_mod
    from app.main import app

    db = SessionLocal()
    marca = uuid.uuid4().hex[:8]
    u = User(nombre="Cobro", correo=f"pago_{marca}@example.com",
             password_hash="x", moneda="COP", pais="CO", plan="free")
    db.add(u)
    db.commit()
    db.refresh(u)
    p = Perfil(user_id=u.id, nombre="Personal", tipo="personal", principal=True)
    db.add(p)
    db.commit()
    uid = u.id

    # El cobro nace DESHABILITADO (sin credenciales), que es como se despliega.
    anteriores = (config_mod.settings.wompi_events_secret,
                  config_mod.settings.wompi_enlace_pro)
    config_mod.settings.wompi_events_secret = SECRETO
    config_mod.settings.wompi_enlace_pro = "https://checkout.wompi.co/l/ABC123"

    tok = create_access_token(uid)
    cliente = TestClient(app)
    h = {"Authorization": f"Bearer {tok}"}
    yield db, cliente, h, uid, Suscripcion
    config_mod.settings.wompi_events_secret, config_mod.settings.wompi_enlace_pro = anteriores
    d = SessionLocal()
    d.query(Suscripcion).filter_by(user_id=uid).delete()
    d.query(Perfil).filter_by(user_id=uid).delete()
    d.query(User).filter_by(id=uid).delete()
    d.commit()
    d.close()


def _pagar(cliente, referencia, status="APPROVED"):
    e = _evento(referencia=referencia, status=status)
    return cliente.post("/api/v1/billing/webhook", json=e)


def test_sin_credenciales_el_cobro_esta_deshabilitado(entorno):
    from app.core import config as config_mod
    db, cliente, h, uid, _ = entorno
    anteriores = config_mod.settings.wompi_enlace_pro
    config_mod.settings.wompi_enlace_pro = ""
    try:
        r = cliente.get("/api/v1/billing/plan", headers=h).json()
        assert r["habilitado"] is False
        assert cliente.post("/api/v1/billing/checkout", headers=h).status_code == 503
    finally:
        config_mod.settings.wompi_enlace_pro = anteriores


def test_checkout_devuelve_la_url_de_wompi_con_la_referencia(entorno):
    db, cliente, h, uid, _ = entorno
    r = cliente.post("/api/v1/billing/checkout", headers=h)
    assert r.status_code == 200
    ref = r.json()["referencia"]
    assert ref.startswith("ctd")
    assert f"ref={ref}" in r.json()["url"]


def test_pagar_activa_pro(entorno):
    db, cliente, h, uid, _ = entorno
    ref = cliente.post("/api/v1/billing/checkout", headers=h).json()["referencia"]
    _pagar(cliente, ref)
    me = cliente.get("/api/v1/auth/me", headers=h).json()
    assert me["plan"] == "pro", "el usuario pago y no quedo PRO"


def test_webhook_con_firma_invalida_no_activa_nada(entorno):
    """El caso de seguridad de punta a punta: evento falso, sin PRO."""
    db, cliente, h, uid, _ = entorno
    ref = cliente.post("/api/v1/billing/checkout", headers=h).json()["referencia"]
    e = _evento(referencia=ref)
    e["data"]["amount_in_cents"] = 1  # manipulado, la firma ya no cuadra
    cliente.post("/api/v1/billing/webhook", json=e)
    assert cliente.get("/api/v1/auth/me", headers=h).json()["plan"] == "free"


def test_pago_rechazado_no_activa(entorno):
    """Un pago DECLINED no puede dejar PRO a nadie."""
    db, cliente, h, uid, _ = entorno
    ref = cliente.post("/api/v1/billing/checkout", headers=h).json()["referencia"]
    _pagar(cliente, ref, status="DECLINED")
    assert cliente.get("/api/v1/auth/me", headers=h).json()["plan"] == "free"


def test_reintento_del_webhook_no_suma_dos_meses(entorno):
    """Wompi reintenta entregas. Sin idempotencia, un reintento regalaba 30 dias."""
    db, cliente, h, uid, _ = entorno
    ref = cliente.post("/api/v1/billing/checkout", headers=h).json()["referencia"]
    _pagar(cliente, ref)
    vence1 = cliente.get("/api/v1/billing/plan", headers=h).json()["vence"]
    for _ in range(3):
        _pagar(cliente, ref)
    assert cliente.get("/api/v1/billing/plan", headers=h).json()["vence"] == vence1


def test_referencia_ajena_no_rompe_nada(entorno):
    db, cliente, h, uid, _ = entorno
    r = _pagar(cliente, "referencia-de-otro")
    assert r.status_code == 200
    assert r.json()["estado"] == "sin-suscripcion"
    assert cliente.get("/api/v1/auth/me", headers=h).json()["plan"] == "free"


def test_cancelar_no_quita_el_acceso_pagado(entorno):
    """Si cancelas el dia 10 de un mes pagado, el acceso sigue hasta el final."""
    db, cliente, h, uid, _ = entorno
    ref = cliente.post("/api/v1/billing/checkout", headers=h).json()["referencia"]
    _pagar(cliente, ref)
    antes = cliente.get("/api/v1/billing/plan", headers=h).json()
    r = cliente.post("/api/v1/billing/cancelar", headers=h, json={}).json()
    despues = cliente.get("/api/v1/billing/plan", headers=h).json()
    assert r["estado"] == "cancelada"
    assert despues["es_pro"] is True, "cobro algo y le cortaron el acceso"
    assert despues["vence"] == antes["vence"]


def test_webhook_responde_200_aun_con_firma_mala(entorno):
    """Para que Wompi deje de reintentar; pero sin activar nada."""
    db, cliente, h, uid, _ = entorno
    r = cliente.post("/api/v1/billing/webhook", json={"event": "transaction.updated"})
    assert r.status_code == 200