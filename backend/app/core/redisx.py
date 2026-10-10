"""Cliente Redis compartido: singleton perezoso.

Devuelve None si Redis no esta disponible, para que cada consumidor degrade sin
romperse (mismo criterio que twofa._r, que ahora delega aqui).
"""
from app.core.config import settings

_cliente = "unset"


def get_redis():
    global _cliente
    if _cliente == "unset":
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
