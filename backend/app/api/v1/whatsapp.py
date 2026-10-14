"""API del bot de WhatsApp.

Tres piezas distintas con tres contratos distintos:

1. El webhook de Meta (`GET` verifica, `POST` recibe). No pide sesion porque
   Meta no tiene usuario ni token: la autenticidad la prueba la firma
   X-Hub-Signature-256 sobre el cuerpo crudo.

2. La vinculacion, que la hace el usuario desde la PWA autenticada: pide un
   codigo, lo pega y queda conectado. El codigo vive en Redis con caducidad
   corta, NO en la base: un PIN de 6 digitos guardado en una tabla es algo que
   alguien con lectura de la base puede usar para quedarse con el numero de
   otra persona.

3. El estado, que la PWA consulta para mostrar si ya esta vinculado.

Mientras no haya credenciales de Meta, todo esto responde 503 sin tocar nada.
"""
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.whatsapp import WhatsappVinculo
from app.services import bot
from app.services import whatsapp as wa

router = APIRouter(tags=["whatsapp"])

# La clave del PIN en Redis y su caducidad. 10 minutos es suficiente para que
# la persona abra la app y lo pegue, y es poco tiempo para que sirva de algo si
# alguien se asoma al celular.
PIN_TTL = 600
PIN_LONGITUD = 6


def _redis():
    try:
        from app.core.redisx import get_redis

        return get_redis()
    except Exception:  # noqa: BLE001
        return None


def _exigir_configurado() -> None:
    if not settings.whatsapp_token or not settings.whatsapp_phone_id:
        raise HTTPException(503, "El bot de WhatsApp todavía no está configurado.")


def _exigir_app_secret() -> None:
    """La firma necesita el App Secret. Sin el, el webhook queda abierto y
    cualquiera usaria el bot; es peor no tener bot que tenerlo abierto."""
    if not settings.whatsapp_app_secret:
        raise HTTPException(503, "Falta WHATSAPP_APP_SECRET: sin él no se puede "
                                 "verificar que el webhook sea legítimo.")


# ---------- webhook de Meta ----------


@router.get("/whatsapp/webhook")
def verificar(mode: str = Query(alias="hub.mode"),
              token: str = Query(alias="hub.verify_token"),
              challenge: str = Query(alias="hub.challenge")):
    """Meta verifica que el webhook sea tuyo antes de empezar a mandar eventos.

    Se compara con `secrets.compare_digest` y no con `==`: este token es lo
    unico que impide que alguien registre la URL de otra persona.
    """
    if not settings.whatsapp_verify_token:
        raise HTTPException(503, "WHATSAPP_VERIFY_TOKEN no está configurado.")
    if mode != "subscribe" or not secrets.compare_digest(token, settings.whatsapp_verify_token):
        raise HTTPException(403, "Verificación fallida.")
    return challenge


@router.post("/whatsapp/webhook")
async def recibir(request: Request, db: Session = Depends(get_db),
                  x_hub_signature_256: str | None = Header(default=None,
                                                          alias="X-Hub-Signature-256")):
    """Recibe mensajes. Siempre 200.

    Meta reintenta lo que no responde 200, y reintentar un mensaje ya procesado
    duplicaria gastos. Por eso se responde 200 siempre y el trabajo real se hace
    dentro, con try/except.
    """
    crudo = await request.body()
    if not wa.habilitado():
        return {"ok": True}
    if not wa.firma_valida(crudo, x_hub_signature_256, settings.whatsapp_app_secret):
        # Firma invalida: se ignora, pero se responde 200 para no provocar un
        # bucle de reintentos desde una IP hostil.
        return {"ok": True}

    import json

    try:
        cuerpo = json.loads(crudo.decode("utf-8"))
    except Exception:
        return {"ok": True}

    for entry in cuerpo.get("entry", []) or []:
        for cambio in entry.get("changes", []) or []:
            valor = cambio.get("value") or {}
            evento = wa.evento_entrante(valor)
            if not evento:
                continue
            _atender(db, evento)
    return {"ok": True}


def _atender(db: Session, evento: dict) -> None:
    """Procesa un mensaje. Envuelve TODO: una excepcion aqui se traduciria en un
    500 y Meta reintentaria el mismo mensaje para siempre."""
    telefono = evento.get("telefono") or ""
    if not telefono:
        return
    texto = evento.get("texto") or ""
    if evento.get("tipo") == "interactive":
        texto = evento.get("texto") or ""
    try:
        respuesta = bot.procesar(db, telefono, texto, evento.get("audio_id"))
    except Exception:  # noqa: BLE001 - el usuario no puede ver un traceback
        respuesta = "Algo salió mal de mi lado. Ya lo reviso."

    vinculo = db.query(WhatsappVinculo).filter_by(telefono=telefono, activo=True).first()
    # Fuera de la ventana de 24h Meta rechaza el mensaje libre. No es un error:
    # es la regla, y avisar por chat seria imposibile.
    if vinculo is not None and not wa.dentro_de_ventana(vinculo.ultimo_bot):
        return
    r = wa.enviar_texto(telefono, respuesta)
    if vinculo is not None and "error" not in (r or {}):
        vinculo.ultimo_bot = datetime.utcnow()
        db.commit()


# ---------- vinculacion desde la PWA ----------


class VincularIn(BaseModel):
    telefono: str = Field(min_length=7, max_length=20)


class ConfirmarIn(BaseModel):
    codigo: str = Field(min_length=4, max_length=10)


def _normalizar(num: str) -> str:
    d = "".join(ch for ch in str(num) if ch.isdigit())
    if not d:
        raise HTTPException(422, "Escribe solo números.")
    # Si llega un celular colombiano sin codigo (10 digitos), se asume 57.
    if len(d) == 10:
        d = "57" + d
    if not 10 <= len(d) <= 15:
        raise HTTPException(422, "Ese número no parece completo. Escríbelo con el código de país.")
    return d


@router.post("/whatsapp/vincular")
def solicitar_codigo(data: VincularIn, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """Guarda el numero, genera el PIN de 6 digitos y lo manda por WhatsApp.

    Guarda Y manda en el mismo paso a proposito. Pedir el numero en un paso y el
    codigo en otro deja dos fuentes de verdad para "cual es mi numero": si el
    usuario se equivoca entre pasos, el PIN se manda a un sitio y se confirma
    contra otro, y el error sale como "codigo incorrecto" cuando el numero esta
    mal.
    """
    _exigir_configurado()
    tel = _normalizar(data.telefono)

    # Un numero no puede quedar atado a dos cuentas.
    if db.query(User).filter(User.telefono == tel, User.id != user.id).first():
        raise HTTPException(409, "Ese número ya está en otra cuenta.")
    if db.query(WhatsappVinculo).filter_by(telefono=tel, activo=True).first():
        raise HTTPException(409, "Ese número está vinculado a otra cuenta.")

    r = _redis()
    if r is None:
        raise HTTPException(503, "No puedo generar el código ahora. Intenta en un momento.")

    codigo = "".join(secrets.choice("0123456789") for _ in range(PIN_LONGITUD))
    r.setex(f"wa:pin:{tel}", PIN_TTL, codigo)
    user.telefono = tel
    db.commit()

    enviado = wa.enviar_texto(
        tel,
        f"Tu código para vincular CTD es *{codigo}*. "
        f"Válido por {PIN_TTL // 60} minutos. Si no fuiste tú, ignórale.",
    )
    if "error" in (enviado or {}):
        raise HTTPException(502, "No pude enviarte el código. Revisa el número.")
    return {"ok": True, "expira_en": PIN_TTL, "telefono": tel,
            "mensaje": f"Te mandé un código al {tel}."}


@router.post("/whatsapp/confirmar-vinculo")
def confirmar_vinculo(data: ConfirmarIn, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """Comprueba el PIN y ata el numero a ESTE usuario."""
    r = _redis()
    if r is None:
        raise HTTPException(503, "No puedo verificar el código ahora.")

    tel = user.telefono
    if not tel:
        raise HTTPException(400, "Primero pide que te mandemos el código.")

    clave = f"wa:pin:{tel}"
    esperado = r.get(clave)
    if not esperado:
        raise HTTPException(410, "El código expiró. Pide uno nuevo.")
    if not secrets.compare_digest(str(esperado), str(data.codigo).strip()):
        raise HTTPException(422, "Ese código no coincide.")

    vinculo = db.query(WhatsappVinculo).filter_by(user_id=user.id, activo=True).first()
    if vinculo is None:
        vinculo = WhatsappVinculo(id=str(uuid.uuid4()), user_id=user.id, telefono=tel,
                                  activo=True)
        db.add(vinculo)
    else:
        vinculo.telefono = tel
        vinculo.activo = True
    r.delete(clave)
    db.commit()

    wa.enviar_texto(tel, "✅ ¡Listo! Ya estamos conectados. Escríbeme lo que "
                         "gastes o ingreses y te lo registro.")
    return {"ok": True, "telefono": tel}


@router.get("/whatsapp/estado")
def estado(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    vinculo = db.query(WhatsappVinculo).filter_by(user_id=user.id, activo=True).first()
    # Se lee del vinculo y no de `users.telefono` a proposito: el vinculo es lo
    # que esta verificado de verdad. Si un numero quedo guardado pero el vinculo
    # se perdio, la app debe decir "no estas conectado", no lo contrario.
    return {
        "configurado": bool(settings.whatsapp_token and settings.whatsapp_phone_id),
        "telefono": vinculo.telefono if vinculo else user.telefono,
        "vinculado": bool(vinculo),
        "desde": vinculo.creado.isoformat() if vinculo else None,
    }


@router.delete("/whatsapp/vinculo")
def quitar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Desvincula. No se borra el numero de `users` a proposito: volver a
    vincular deberia ser volver a pegar un codigo, no volver a escribir el numero."""
    db.query(WhatsappVinculo).filter_by(user_id=user.id, activo=True).update(
        {"activo": False})
    db.commit()
    return {"ok": True}