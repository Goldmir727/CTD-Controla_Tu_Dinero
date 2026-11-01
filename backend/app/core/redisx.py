"""Cliente Redis compartido: singleton perezoso.

Devuelve None si Redis no esta disponible, para que cada consumidor degrade sin
romperse (mismo criterio que twofa._r, que ahora delega aqui).
"""
import os

from app.core.config import settings

_cliente = "unset"


def _url_utilizable() -> bool:
    """Evita perder 2s por cold start intentando un Redis que no existe.

    En Docker el default apunta al servicio `redis` (o al que diga REDIS_URL).
    En Vercel, si nadie configuro REDIS_URL, el default `localhost` no existe.
    """
    url = (settings.redis_url or "").strip()
    if not url:
        return False
    if os.getenv("VERCEL") and ("localhost" in url or "127.0.0.1" in url):
        return False
    return True


def get_redis():
    global _cliente
    if _cliente == "unset":
        if not _url_utilizable():
            _cliente = None
            return None
        try:
            import redis

            c = redis.Redis.from_url(
                settings.redis_url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True
            )
            c.ping()
            _cliente = c
        except Exception:
            _cliente = None
    return _cliente
