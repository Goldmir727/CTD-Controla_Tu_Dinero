"""WhatsApp Cloud API de Meta: firma, mensajes y envio.

Lo unico que hay que acertar aca es la FIRMA. El webhook de Meta trae
`X-Hub-Signature-256`, que es `sha256=` seguido del HMAC-SHA256 del cuerpo CRUDO
usando el App Secret. Sin verificarla, cualquiera que mande un POST a
`/whatsapp/webhook` podria usar el bot y gastar la clave de la IA a tu costa.

Detalle que hace fallar esto si no se cuida: el HMAC es del cuerpo EXACTO que
llego. No de un re-serializado con otro orden de llaves. Por eso se calcula
sobre `request.body()` crudo y no sobre el dict parseado.

La ventana de 24 horas: WhatsApp solo deja mandar mensajes libres dentro de las
24h posteriores a haber contestado al usuario. Pasado eso hay que usar plantilla
aprobada. `dentro_de_ventana()` es lo que decide si el bot puede hablar por su
cuenta o si tiene que callarse.
"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

GRAPH = "https://graph.facebook.com/v21.0"


def habilitado() -> bool:
    from app.core.config import settings

    return bool(settings.whatsapp_token and settings.whatsapp_phone_id
                and settings.whatsapp_app_secret)


def firma_valida(cuerpo_crudo: bytes, cabecera: str | None, app_secret: str) -> bool:
    """Comprueba X-Hub-Signature-256 contra el cuerpo crudo."""
    if not cabecera or not app_secret:
        return False
    esperado = "sha256=" + hmac.new(
        app_secret.encode("utf-8"), cuerpo_crudo, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, cabecera)


def normalizar_telefono(wa_id: str | None) -> str:
    """'573001234567' -> '573001234567'. Solo digitos.

    Meta manda el numero sin '+'. Se limpia igual para no confiar de mas en el
    formato de entrada.
    """
    return "".join(ch for ch in str(wa_id or "") if ch.isdigit())


# ---------- leer lo que llega ----------


def _primer(mensaje: dict) -> dict:
    """Meta agrupa en 'messages' y 'statuses'; y un webhook de texto puede traer
    'messages' con varios. Se procesa el primero: el bot es de un turno."""
    mensajes = mensaje.get("messages") or []
    return mensajes[0] if mensajes else {}


def evento_entrante(mensaje: dict) -> dict | None:
    """Saca (telefono, tipo, texto, audio_id, id_mensaje) o None si no es entrada.

    Se ignoran a proposito los `statuses` (entregado/leido), que llegan a la
    misma URL y no son mensajes del usuario.
    """
    m = _primer(mensaje)
    if not m:
        return None
    if m.get("type") not in ("text", "audio", "interactive", "button"):
        return None
    cuerpo = m.get("text") or {}
    return {
        "telefono": normalizar_telefono(m.get("from")),
        "tipo": m.get("type"),
        "texto": (cuerpo.get("body") or "").strip(),
        "audio_id": (m.get("audio") or {}).get("id"),
        "id": m.get("id") or "",
        "timestamp": m.get("timestamp"),
    }


def texto_de_interactivo(m: dict) -> str:
    """Un boton o lista responde con un title/selected; a veces con un id."""
    interactivo = m.get("interactive") or {}
    respuesta = interactivo.get("button_reply") or interactivo.get("list_reply") or {}
    return str(respuesta.get("title") or respuesta.get("id") or "").strip()


# ---------- la ventana de 24 horas ----------


def dentro_de_ventana(ultimo_bot: datetime | None) -> bool:
    """True si todavia se puede responder libre (24h desde el ultimo del bot)."""
    if ultimo_bot is None:
        return False
    if ultimo_bot.tzinfo is not None:
        ultimo_bot = ultimo_bot.astimezone(timezone.utc).replace(tzinfo=None)
    return datetime.utcnow() - ultimo_bot <= timedelta(hours=24)


# ---------- enviar ----------

def _token() -> str:
    from app.core.config import settings

    return settings.whatsapp_token


def _phone_id() -> str:
    from app.core.config import settings

    return settings.whatsapp_phone_id


def enviar_texto(destino: str, texto: str) -> dict:
    """POST a /messages. Devuelve el JSON de la Graph o el error, nunca lanza.

    Lanza sería peor: el webhook de Meta devolveria 500 y reintentaria el mismo
    mensaje para siempre, y el usuario veria el texto dos veces.
    """
    import httpx

    payload = {
        "messaging_product": "whatsapp",
        "to": destino,
        "type": "text",
        "text": {"preview_url": False, "body": texto[:4096]},
    }
    try:
        r = httpx.post(f"{GRAPH}/{_phone_id()}/messages",
                       json=payload,
                       headers={"Authorization": f"Bearer {_token()}",
                                "Content-Type": "application/json"},
                       timeout=15)
        return r.json()
    except Exception as e:  # noqa: BLE001
        return {"error": {"message": str(e)}}


def enviar_audio(destino: str, audio: bytes, mime: str = "audio/ogg") -> dict:
    """Nota de voz de respuesta. Requiere que el template de audio este aprobado
    en Meta; si no, la API lo rechaza y hay que recurrir a texto."""
    import httpx

    try:
        r = httpx.post(f"{GRAPH}/{_phone_id()}/messages",
                       headers={"Authorization": f"Bearer {_token()}",
                                "Content-Type": mime},
                       files={"messaging_product": (None, "whatsapp"),
                              "to": (None, destino),
                              "type": (None, "audio"),
                              "audio": ("nota.ogg", audio, mime)},
                       data={"audio": "nota.ogg"},
                       timeout=30)
        return r.json()
    except Exception as e:  # noqa: BLE001
        return {"error": {"message": str(e)}}


def descargar_audio(audio_id: str) -> tuple[bytes, str]:
    """Baja la nota de voz de Meta. Devuelve (bytes, mime)."""
    import httpx

    r = httpx.get(f"{GRAPH}/{audio_id}", headers={"Authorization": f"Bearer {_token()}"},
                  timeout=30)
    r.raise_for_status()
    meta = r.json()
    url = meta.get("url") or ""
    mime = meta.get("mime_type") or "audio/ogg"
    if not url:
        raise ValueError("Meta no devolvio la URL del audio")
    b = httpx.get(url, timeout=60)
    b.raise_for_status()
    return b.content, mime


def resumir_error(respuesta: dict) -> str:
    """Traduce el error de la Graph a algo que valga para un log."""
    err = respuesta.get("error") or {}
    detalle = (err.get("error_data") or {}).get("details") or err.get("message") or ""
    codigo = err.get("code") or ""
    if codigo == 131026:
        return "Plantilla de mensaje no aprobada por Meta"
    if "outside" in str(detalle).lower() or "24" in str(detalle):
        return "Fuera de la ventana de 24 horas"
    return f"{codigo}: {detalle}".strip(": ")


def resumen_mensaje(ev: dict[str, Any]) -> dict:
    """Lo minimo para loguear, sin volcar audio ni PII de mas."""
    return {"tipo": ev.get("tipo"), "id": ev.get("id"),
            "largo": len(ev.get("texto") or ""), "audio": bool(ev.get("audio_id"))}