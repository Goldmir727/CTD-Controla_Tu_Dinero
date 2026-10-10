"""2FA email: código 6 dígitos, 10min, 5 intentos, cooldown 60s entre envíos.

Backend primario: Redis (claves temporales con TTL, ideal para esto).
Fallback: Postgres (tabla two_fa_codes) si Redis no está disponible.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redisx import get_redis
from app.models.twofa import TwoFaCode
from app.services.email import send_2fa_code


class CooldownError(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"Espera {retry_after}s para pedir otro código.")
        self.retry_after = retry_after


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


_redis = "unset"


def _r():
    return get_redis()


def _keys(user_id: str) -> tuple[str, str, str]:
    return f"2fa:code:{user_id}", f"2fa:att:{user_id}", f"2fa:cd:{user_id}"


def emitir(db: Session | None, user_id: str, correo: str) -> None:
    code = f"{secrets.randbelow(1_000_000):06d}"
    r = _r()
    if r is not None:
        ck, _, cd = _keys(user_id)
        ttl = r.ttl(cd)
        if ttl and ttl > 0:
            raise CooldownError(int(ttl))
        ttl_s = settings.twofa_ttl_min * 60
        r.setex(ck, ttl_s, _hash(code))
        r.setex(cd, settings.twofa_cooldown_s, "1")
        try:
            send_2fa_code(correo, code)
        except Exception:
            r.delete(ck, cd)  # no se envió: permite reintento inmediato
            raise
        return
    # Fallback Postgres (solo dev sin redis)
    assert db is not None
    db.query(TwoFaCode).filter_by(user_id=user_id, used=False).update({"used": True})
    db.add(TwoFaCode(user_id=user_id, code_hash=_hash(code),
                     expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=settings.twofa_ttl_min)))
    db.commit()
    send_2fa_code(correo, code)


def verificar(db: Session | None, user_id: str, code: str) -> bool:
    r = _r()
    if r is not None:
        ck, ak, _ = _keys(user_id)
        h = r.get(ck)
        if not h:
            return False
        n = r.incr(ak)
        if n == 1:
            r.expire(ak, settings.twofa_ttl_min * 60)
        if n > settings.twofa_max_attempts:
            r.delete(ck, ak)
            return False
        if h == _hash(code.strip()):
            r.delete(ck, ak)
            return True
        return False
    assert db is not None
    row = db.query(TwoFaCode).filter_by(user_id=user_id, used=False).order_by(TwoFaCode.expires_at.desc()).first()
    if not row:
        return False
    if datetime.utcnow() > row.expires_at or row.attempts >= settings.twofa_max_attempts:
        row.used = True
        db.commit()
        return False
    row.attempts += 1
    if row.code_hash == _hash(code.strip()):
        row.used = True
        db.commit()
        return True
    db.commit()
    return False
