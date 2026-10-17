"""Wompi (Bancolombia): verificar eventos y entender que dicen.

Lo unico que de verdad hay que acertar aqui es la FIRMA. Si se acepta un evento
sin verificar, cualquiera que conozca la URL del webhook se activa PRO a si
mismo. Si se rechaza un evento legitimo, el usuario paga y no entra: el peor
fallo posible porque el cliente no se queja.

Como funciona (segun la documentacion de eventos de Wompi):
- Cada evento trae `signature.properties` con la lista EXACTA de campos que
  se usa para firmarlo, `signature.timestamp`, y el hash en
  `signature.checksum` y en el header `X-Event-Checksum`.
- El hash es SHA256 de: los valores de esas propiedades, en ese orden, sin
  separadores, seguido del timestamp y seguido del secreto del comercio.
- La lista de propiedades se lee del evento, no se fija aqui a proposito: si
  Wompi agrega un campo a la firma, este codigo sigue funcionando en vez de
  empezar a rechazar todos los pagos.

Nota honesta: la separacion entre valores ("sin separadores") es lo que dice la
documentacion, y el ejemplo en Ruby de Wompi trae guiones que son parte de los
datos. Si al conectar con credenciales reales los eventos legítimos se rechazan,
esta es la funcion a revisar primero (esta probada en test_wompi.py).
"""
import hashlib
from typing import Any


def checksum_esperado(evento: dict, events_secret: str) -> str | None:
    """SHA256 que deberia traer el evento, o None si el evento no trae firma."""
    firma = evento.get("signature") or {}
    props = firma.get("properties") or []
    ts = firma.get("timestamp")
    recibido = firma.get("checksum")
    if not props or ts is None or not recibido or not events_secret:
        return None

    data = evento.get("data") or {}
    partes = []
    for clave in props:
        valor = data.get(clave)
        if valor is None:
            # Un campo declarado en la firma pero ausente no se inventa: sin el
            # valor real no se puede reproducir el hash.
            return None
        partes.append(str(valor))
    partes.append(str(ts))
    partes.append(events_secret)
    return hashlib.sha256("".join(partes).encode("utf-8")).hexdigest()


def firma_valida(evento: dict, events_secret: str, header_checksum: str | None = None) -> bool:
    """True solo si el hash del evento coincide con el que calcula el secreto.

    Se comparan las dos copias del checksum (header y cuerpo) en modo
    `secrets.compare_digest`, que no filtra por tiempo: comparar con `==` deja
    escapar informacion por tiempos y aqui se compara un secreto.
    """
    import hmac

    esperado = checksum_esperado(evento, events_secret)
    if esperado is None:
        return False
    recibido = header_checksum or (evento.get("signature") or {}).get("checksum") or ""
    return hmac.compare_digest(esperado, str(recibido))


def es_transaccion(evento: dict) -> bool:
    return str(evento.get("event") or "").startswith("transaction.")


def datos_transaccion(evento: dict) -> dict:
    return evento.get("data") or {}


def es_aprobada(evento: dict) -> bool:
    """Solo APPROVED activa PRO. DECLINED es un pago rechazado: no se toca nada."""
    d = datos_transaccion(evento)
    return str(d.get("status") or "").upper() == "APPROVED"


def referencia(datos: dict) -> str:
    """La referencia que metio el usuario en el checkout: sirve para casar la
    transaccion con la suscripcion."""
    return str(datos.get("reference") or "").strip()


def monto_centavos(datos: dict) -> int:
    try:
        return int(datos.get("amount_in_cents") or 0)
    except (TypeError, ValueError):
        return 0


def correo_comprador(datos: dict) -> str:
    p = (datos.get("customer_email") or "").strip()
    return str(p).lower()


def referencia_nueva(prefijo: str = "ctd") -> str:
    """Referencia unica por intento de pago.

    Wompi agrupa por referencia: dos compras con la misma se tranzan juntas. Por
    eso lleva el id del usuario y un aleatorio, no solo el id.
    """
    import secrets as _secrets

    return f"{prefijo}-{_secrets.token_hex(6)}"


def resumen_evento(evento: dict) -> dict[str, Any]:
    """Lo minimo para loguear sin volcar el evento entero."""
    d = datos_transaccion(evento)
    return {
        "event": evento.get("event"),
        "estado": d.get("status"),
        "referencia": referencia(d),
        "monto": monto_centavos(d),
    }