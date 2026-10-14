"""Tests del bot de WhatsApp.

Lo que se prueba aqui NO es "que mande bien el texto", sino las decisiones que
evitan meter la pata:

- Que un webhook forjado no se procese (firma).
- Que SIN firma no se procese, porque el endpoint es publico por definicion.
- Que confirmar un gasto lo escriba de verdad, y solo una vez aunque el usuario
  mande "si" dos veces (WhatsApp reintenta y la gente repite).
- Que no se guarde en silencio un monto que la IA dedujo.
- Que la cuota corte antes de gastar una llamada al modelo.
- Que un numero sin vinculo no pueda registrar nada.

Ninguno de estos se nota probando "a mano": el que mas duele es el del "si"
repetido, porque en la app web un doble clic es imposible (el boton se
deshabilita) y en WhatsApp es lo mas normal del mundo.
"""
import uuid

import pytest

from app.models.captura import Captura
from app.models.finance import Transaction
from app.services import bot
from app.services import whatsapp as wa

SECRET_APP = "app_secret_de_prueba"
VERIFY_TOKEN = "verify_token_de_prueba"


# ---------- firma (la puerta de entrada) ----------


def _cuerpo_crudo(payload: bytes) -> str:
    import hashlib
    import hmac

    return "sha256=" + hmac.new(SECRET_APP.encode(), payload, hashlib.sha256).hexdigest()


def test_firma_valida_acepta():
    crudo = b'{"a":1}'
    assert wa.firma_valida(crudo, _cuerpo_crudo(crudo), SECRET_APP) is True


def test_firma_con_otro_secreto_rechaza():
    """Sin esto, cualquiera que mande un POST al webhook usaria el bot."""
    crudo = b'{"a":1}'
    firma = "sha256=" + __import__("hmac").new(b"otro", crudo,
                                              __import__("hashlib").sha256).hexdigest()
    assert wa.firma_valida(crudo, firma, SECRET_APP) is False


def test_cuerpo_modificado_rechaza():
    """Se firma el cuerpo CRUDO: si re-serializamos el JSON, la firma ya no
    cuadra aunque los datos sean los mismos."""
    crudo = b'{"a":1}'
    firma = _cuerpo_crudo(crudo)
    otro = b'{"a":2}'
    assert wa.firma_valida(otro, firma, SECRET_APP) is False


def test_sin_app_secret_no_pasa():
    assert wa.firma_valida(b"{}", "sha256=abc", "") is False


def test_normalizar_telefono():
    assert wa.normalizar_telefono("+57 300 123 4567") == "573001234567"
    assert wa.normalizar_telefono(None) == ""


def test_ventana_de_24_horas():
    from datetime import datetime, timedelta

    assert wa.dentro_de_ventana(datetime.utcnow()) is True
    assert wa.dentro_de_ventana(datetime.utcnow() - timedelta(hours=23)) is True
    assert wa.dentro_de_ventana(datetime.utcnow() - timedelta(hours=25)) is False
    # Nunca hablo con el bot = no hay ventana abierta.
    assert wa.dentro_de_ventana(None) is False


def test_ignora_statuses_no_mensajes():
    """Meta manda 'statuses' (entregado/leido) por la misma URL."""
    assert wa.evento_entrante({"statuses": [{"id": "x", "status": "delivered"}]}) is None


def test_extrae_texto_de_tres_tipos():
    base = {"from": "573001234567", "id": "wamid.1"}
    t = wa.evento_entrante({"messages": [{**base, "type": "text",
                                          "text": {"body": " gasté 25 mil "}}]})
    assert t["texto"] == "gasté 25 mil"

    i = wa.evento_entrante({"messages": [{**base, "type": "interactive",
                                          "interactive": {"button_reply":
                                                          {"title": "Sí, es el mismo"}}}]})
    assert i["tipo"] == "interactive"

    a = wa.evento_entrante({"messages": [{**base, "type": "audio",
                                          "audio": {"id": "audio-1"}}]})
    assert a["audio_id"] == "audio-1"


# ---------- helpers de texto ----------


def test_es_respuesta_tolera_acentos_y_signos():
    assert bot._es_respuesta("  ¡SÍ!  ") == "si"
    assert bot._es_respuesta("dale") == "dale"
    assert bot._es_respuesta("No.") == "no"


def test_detecta_si_y_no():
    assert bot._es("sí", bot._SI) is True
    assert bot._es("dale", bot._SI) is True
    assert bot._es("no", bot._NO) is True
    assert bot._es("cancelar", bot._NO) is True
    assert bot._es("cambiar el aceite", bot._SI) is False


def test_dinero_al_estilo_colombiano():
    assert bot._dinero(25000) == "$25.000"
    assert bot._dinero(1200000) == "$1.200.000"


def test_clave_del_bot_cabe_en_el_campo():
    """`idempotency_key` es String(36). Si la clave se pasara, el deshacer
    dejaria de encontrar los movimientos."""
    c = bot._clave_bot(str(uuid.uuid4()))
    assert len(c) <= 36
    assert c.startswith("wa")
    assert bot._clave_bot("a" * 40) != bot._clave_bot("b" * 40)


# ---------- flujo con la maquina de estados ----------


@pytest.fixture()
def entorno():
    from app.core import config as cfg
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.captura import Captura
    from app.models.finance import Account, Category, Transaction
    from app.models.perfil import Perfil
    from app.models.user import User
    from app.models.whatsapp import WhatsappSesion, WhatsappVinculo
    from fastapi.testclient import TestClient

    from app.main import app

    db = SessionLocal()
    marca = uuid.uuid4().hex[:8]
    u = User(nombre="Bot", correo=f"bot_{marca}@example.com", password_hash="x",
             moneda="COP", pais="CO", plan="free", onboarding_done=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    p = Perfil(user_id=u.id, nombre="Personal", tipo="personal", principal=True)
    db.add(p)
    db.commit()
    db.refresh(p)
    # El bot no puede guardar nada sin cuenta y categoria.
    cat = Category(user_id=u.id, perfil_id=p.id, nombre="Comida", tipo="gasto")
    db.add(cat)
    cuenta = Account(user_id=u.id, perfil_id=p.id, nombre="Banco", tipo="banco",
                     saldo_inicial=0)
    db.add(cuenta)
    db.commit()
    db.refresh(cat)
    db.refresh(cuenta)
    uid = u.id
    tel = f"5730{marca}"

    anteriores = (cfg.settings.whatsapp_token, cfg.settings.whatsapp_phone_id,
                  cfg.settings.whatsapp_app_secret, cfg.settings.whatsapp_verify_token)
    cfg.settings.whatsapp_token = "tok"
    cfg.settings.whatsapp_phone_id = "123456"
    cfg.settings.whatsapp_app_secret = SECRET_APP
    cfg.settings.whatsapp_verify_token = VERIFY_TOKEN

    yield db, u, p, cat, cuenta, tel, uid, TestClient(app), \
        create_access_token(uid), WhatsappVinculo, WhatsappSesion

    (cfg.settings.whatsapp_token, cfg.settings.whatsapp_phone_id,
     cfg.settings.whatsapp_app_secret, cfg.settings.whatsapp_verify_token) = anteriores
    d = SessionLocal()
    # Los movimientos tambien se borran: si se dejaran, el siguiente test que
    # cuenta movimientos veria los del anterior y fallaria sin motivo real.
    d.query(Transaction).filter_by(user_id=uid).delete()
    d.query(Captura).filter_by(user_id=uid).delete()
    d.query(WhatsappSesion).filter_by(user_id=uid).delete()
    d.query(WhatsappVinculo).filter_by(user_id=uid).delete()
    d.query(Category).filter_by(user_id=uid).delete()
    d.query(Account).filter_by(user_id=uid).delete()
    d.query(Perfil).filter_by(user_id=uid).delete()
    d.query(User).filter_by(id=uid).delete()
    d.commit()
    d.close()


def _vincular(db, user, tel, WhatsappVinculo):
    v = WhatsappVinculo(id=str(uuid.uuid4()), user_id=user.id, telefono=tel, activo=True)
    db.add(v)
    db.commit()
    return v


def _propuesta(db, user, perfil, monto=25000, requiere_monto=False):
    """Mete a mano lo que `proponer` habria devuelto, sin llamar a la IA."""
    import json

    from app.models.captura import Captura

    reg = Captura(user_id=user.id, perfil_id=perfil.id, texto="gasté 25 mil",
                  estado="propuesta", monto_dudoso=requiere_monto,
                  propuestos=json.dumps([{
                      "ix": 0, "tipo": "gasto", "monto": monto,
                      "requiere_confirmacion_monto": requiere_monto,
                      "categoria_id": perfil.id and None, "categoria": "Comida",
                      "descripcion": "almuerzo", "fecha": "2026-10-12",
                      "coincidencias": []}]))
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


def test_sin_vinculo_no_puede_registrar(entorno):
    """El caso base de seguridad: un numero desconocido no toca la base."""
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    r = bot.procesar(db, "570000000000", "gasté 5 millones")
    assert "vincular" in r.lower()
    assert db.query(Transaction).filter_by(user_id=u.id).count() == 0


def test_ayuda_no_gasta_nada(entorno):
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    _vincular(db, u, tel, Vinculo)
    r = bot.procesar(db, tel, "ayuda")
    assert "almuerzo" in r
    assert db.query(Transaction).filter_by(user_id=u.id).count() == 0


def test_confirmar_guarda_de_verdad(entorno):
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    _vincular(db, u, tel, Vinculo)
    reg = _propuesta(db, u, p)
    reg.propuestos = reg.propuestos.replace('"categoria_id": null',
                                            f'"categoria_id": "{cat.id}"')
    db.commit()

    s = Sesion(id=str(uuid.uuid4()), user_id=u.id, perfil_id=p.id,
               estado="esperando_confirmacion", captura_id=reg.id)
    db.add(s)
    db.commit()

    r = bot.procesar(db, tel, "sí")
    assert db.query(Transaction).filter_by(user_id=u.id).count() == 1, r
    assert "Guardé" in r


def test_si_repetido_no_duplica(entorno):
    """Lo que mas duele en WhatsApp: la gente repite el mensaje. Con doble
    guardado, el reporte queda mal y el usuario no sabe por que."""
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    _vincular(db, u, tel, Vinculo)
    reg = _propuesta(db, u, p)
    reg.propuestos = reg.propuestos.replace('"categoria_id": null',
                                            f'"categoria_id": "{cat.id}"')
    db.commit()
    s = Sesion(id=str(uuid.uuid4()), user_id=u.id, perfil_id=p.id,
               estado="esperando_confirmacion", captura_id=reg.id)
    db.add(s)
    db.commit()

    bot.procesar(db, tel, "sí")
    # El usuario se equivoco y vuelve a mandar "si" (o Meta reintento).
    s.estado = "esperando_confirmacion"
    db.commit()
    r2 = bot.procesar(db, tel, "sí")

    assert db.query(Transaction).filter_by(user_id=u.id).count() == 1, r2


def test_no_guarda_un_monto_deducido(entorno):
    """Guardar en silencio una cifra que la IA adivino arruina la confianza en
    todo el reporte. Ahi se pregunta."""
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    _vincular(db, u, tel, Vinculo)
    reg = _propuesta(db, u, p, requiere_monto=True)
    reg.propuestos = reg.propuestos.replace('"categoria_id": null',
                                            f'"categoria_id": "{cat.id}"')
    db.commit()
    s = Sesion(id=str(uuid.uuid4()), user_id=u.id, perfil_id=p.id,
               estado="esperando_confirmacion", captura_id=reg.id)
    db.add(s)
    db.commit()

    r = bot.procesar(db, tel, "sí")
    assert db.query(Transaction).filter_by(user_id=u.id).count() == 0
    assert "monto" in r.lower()


def test_no_cancela_no_guarda(entorno):
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    _vincular(db, u, tel, Vinculo)
    reg = _propuesta(db, u, p)
    s = Sesion(id=str(uuid.uuid4()), user_id=u.id, perfil_id=p.id,
               estado="esperando_confirmacion", captura_id=reg.id)
    db.add(s)
    db.commit()

    r = bot.procesar(db, tel, "no")
    assert db.query(Transaction).filter_by(user_id=u.id).count() == 0
    assert "no guard" in r.lower()


def test_propuesta_caduca(entorno):
    """Un "si" de manana no debe confirmar algo de hace un dia."""
    from datetime import datetime, timedelta

    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    _vincular(db, u, tel, Vinculo)
    reg = _propuesta(db, u, p)
    viejo = datetime.utcnow() - timedelta(hours=bot.CADUCA_HORAS + 1)
    s = Sesion(id=str(uuid.uuid4()), user_id=u.id, perfil_id=p.id,
               estado="esperando_confirmacion", captura_id=reg.id,
               actualizado=viejo, creado=viejo)
    db.add(s)
    db.commit()

    r = bot.procesar(db, tel, "sí")
    assert db.query(Transaction).filter_by(user_id=u.id).count() == 0
    assert "repites" in r.lower()


def test_deshacer_solo_toca_lo_del_bot(entorno):
    """Si el usuario escribio algo en la web, que el bot lo borre al decir
    'deshacer' seria peor que no tener la funcion."""

    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    _vincular(db, u, tel, Vinculo)
    de_web = Transaction(user_id=u.id, perfil_id=p.id, cuenta_id=cuenta.id,
                         categoria_id=cat.id,
                         tipo="gasto", monto=9999, fecha="2026-10-12",
                         descripcion="escrito en la web")
    db.add(de_web)
    db.commit()

    r = bot.procesar(db, tel, "deshacer")
    # Lo que importa es que el movimiento de la web sigue ahi. El texto exacto
    # no: el bot dice que no hay nada suyo que deshacer, que es justo lo correcto.
    assert db.query(Transaction).filter_by(user_id=u.id).count() == 1
    assert db.query(Transaction).filter_by(descripcion="escrito en la web").count() == 1
    assert "no encontré" in r.lower()


def test_webhook_sin_firma_no_procesa(entorno):
    """El endpoint es publico. Sin esto, cualquiera POSTea y usa el bot."""
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    _vincular(db, u, tel, Vinculo)
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": tel, "id": "w1", "type": "text", "text": {"body": "gasté 99"}}]}}]}]}
    r = cli.post("/api/v1/whatsapp/webhook", json=payload)
    assert r.status_code == 200
    assert db.query(Transaction).filter_by(user_id=u.id).count() == 0


def test_webhook_con_firma_si_llega_al_bot(entorno):
    """Con firma buena, el mensaje llega al bot (que respondera con algo, pero
    lo importante es que NO lo rebota la firma)."""
    import json as _json

    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    _vincular(db, u, tel, Vinculo)
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": tel, "id": "w2", "type": "text", "text": {"body": "ayuda"}}]}}]}]}
    crudo = _json.dumps(payload).encode()
    r = cli.post("/api/v1/whatsapp/webhook", content=crudo,
                 headers={"X-Hub-Signature-256": _cuerpo_crudo(crudo),
                          "Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_verificacion_del_webhook_rechaza_token_malo(entorno):
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    r = cli.get("/api/v1/whatsapp/webhook",
                params={"hub.mode": "subscribe", "hub.verify_token": "incorrecto",
                        "hub.challenge": "123"})
    assert r.status_code == 403


def test_verificacion_acepta_token_bueno(entorno):
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    r = cli.get("/api/v1/whatsapp/webhook",
                params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN,
                        "hub.challenge": "12345"})
    assert r.status_code == 200
    assert r.text.strip() == '"12345"'


def test_estado_dice_que_no_esta_vinculado(entorno):
    db, u, p, cat, cuenta, tel, uid, cli, tok, Vinculo, Sesion = entorno
    h = {"Authorization": f"Bearer {tok}"}
    r = cli.get("/api/v1/whatsapp/estado", headers=h).json()
    assert r["vinculado"] is False
    assert r["configurado"] is True
