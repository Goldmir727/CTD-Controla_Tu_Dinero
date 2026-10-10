"""Rate-limit MVP en memoria (por IP). Para multi-worker usar Redis en Fase 4."""
import time
from collections import defaultdict

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = defaultdict(list)


def _limit(key: str, max_n: int, window_s: int):
    async def dep(request: Request):
        now = time.monotonic()
        host = request.client.host if request.client else "?"
        k = f"{key}:{host}"
        arr = [t for t in _hits[k] if now - t < window_s]
        if len(arr) >= max_n:
            raise HTTPException(429, "Demasiados intentos. Espera un momento.")
        arr.append(now)
        _hits[k] = arr

    return dep


# Login: 10/min por IP. Códigos 2FA: 10/10min (solicitar) y 10/min (verificar comparte TTL del código + 5 intentos por código).
login_limit = _limit("login", 10, 60)
solicitar_limit = _limit("2fa-sol", 10, 600)
verificar_limit = _limit("2fa-ver", 10, 60)
pw_solicitar_limit = _limit("pw-sol", 5, 600)
pw_confirmar_limit = _limit("pw-ver", 10, 60)
# Asesor IA: tope diario por IP (el tope por usuario/plan llega con el paywall)
asesor_limit = _limit("asesor", 20, 86400)
