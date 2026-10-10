"""Entitlements de plan (free/pro) y cuotas por usuario.

Activacion manual por ahora: no hay pasarela de pago. El campo users.plan queda
listo para que el checkout futuro solo lo actualice, sin cambiar endpoints.

Decisiones de producto:
- El asesor CON herramientas (function calling) es gratis pero limitado: es el anzuelo.
  Lo de pago son los reportes detallados y los documentos (Excel/PDF).
- Si Redis no responde, la cuota diaria del asesor cae a contar filas en Postgres
  (asesor_mensajes) en vez de dejarlo sin limite.
"""
from datetime import date, datetime, timedelta

from fastapi import Depends, HTTPException

from app.core.deps import get_current_user
from app.core.redisx import get_redis
from app.models.asesor import AsesorMensaje
from app.models.captura import Captura
from app.models.user import User

PLANES: dict[str, dict] = {
    "free": {
        "etiqueta": "Gratis",
        "asesor_dia": 5,
        "captura_dia": 15,
        "reportes_detallados": False,
        "export_excel": False,
        "export_pdf": False,
        "fijos": True,
    },
    "pro": {
        "etiqueta": "PRO",
        "asesor_dia": 100,
        "captura_dia": 200,
        "reportes_detallados": True,
        "export_excel": True,
        "export_pdf": True,
        "fijos": True,
    },
}


def plan_efectivo(user: User) -> str:
    """free si no es pro, o si el pro ya vencio."""
    if getattr(user, "plan", "free") != "pro":
        return "free"
    if user.plan_vencimiento and user.plan_vencimiento < datetime.utcnow():
        return "free"
    return "pro"


def config_plan(user: User) -> dict:
    return PLANES[plan_efectivo(user)]


def es_pro(user: User) -> bool:
    return plan_efectivo(user) == "pro"


def require_plan(feature: str, mensaje: str | None = None):
    """Dependencia que bloquea una feature de PRO con 402."""

    def dep(user: User = Depends(get_current_user)) -> User:
        if not config_plan(user).get(feature):
            raise HTTPException(
                402,
                mensaje or f"'{feature}' es una función PRO. Activa tu plan PRO para usarla.",
            )
        return user

    return dep


# ---- Cuotas ----
def _clave_dia(user_id: str, recurso: str) -> str:
    return f"cuota:{user_id}:{recurso}:{date.today().isoformat()}"


def _contar_hoy(db, user_id: str, recurso: str) -> int:
    """Fallback en Postgres cuando Redis no responde. Sin esto, una caida de Redis
    dejaria al usuario sin limite."""
    desde = datetime.combine(date.today(), datetime.min.time())
    if recurso == "asesor":
        return int(
            db.query(AsesorMensaje)
            .filter(AsesorMensaje.user_id == user_id, AsesorMensaje.rol == "user",
                    AsesorMensaje.created_at >= desde)
            .count()
        )
    if recurso == "captura":
        return int(
            db.query(Captura)
            .filter(Captura.user_id == user_id, Captura.created_at >= desde)
            .count()
        )
    return 0


def _limite(user: User, recurso: str) -> int:
    cfg = config_plan(user)
    return int(cfg.get(f"{recurso}_dia", 0))


def consumo(db, user: User, recurso: str) -> dict:
    """Uso de hoy: {usado, limite, plan, queda}."""
    limite = _limite(user, recurso)
    r = get_redis()
    usado = None
    if r is not None:
        try:
            usado = int(r.get(_clave_dia(user.id, recurso)) or 0)
        except Exception:
            usado = None
    if usado is None:
        usado = _contar_hoy(db, user.id, recurso)
    return {"usado": usado, "limite": limite, "plan": plan_efectivo(user),
            "queda": max(limite - usado, 0)}


def consumir(db, user: User, recurso: str) -> dict:
    """Suma 1 al consumo de hoy. Lanza 429 si ya agoto la cuota."""
    estado = consumo(db, user, recurso)
    if estado["limite"] and estado["usado"] >= estado["limite"]:
        raise HTTPException(
            429,
            f"Llegaste al límite de {estado['limite']} {recurso}s por hoy. "
            "Se reinicia mañana o activa PRO para más.",
        )
    r = get_redis()
    if r is not None:
        try:
            clave = _clave_dia(user.id, recurso)
            # TTL hasta medianoche local + 1h de holgura
            ttl = int((datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
                       - datetime.now()).total_seconds()) + 3600
            usado = int(r.incr(clave))
            r.expire(clave, max(ttl, 3600))
            return {"usado": usado, "limite": estado["limite"], "plan": estado["plan"],
                    "queda": max(estado["limite"] - usado, 0)}
        except Exception:
            pass  # cae al conteo en Postgres
    estado["usado"] += 1
    estado["queda"] = max(estado["limite"] - estado["usado"], 0)
    return estado


def consumo_asesor(db, user: User) -> dict:
    return consumo(db, user, "asesor")


def consumir_asesor(db, user: User) -> dict:
    return consumir(db, user, "asesor")


def consumo_captura(db, user: User) -> dict:
    return consumo(db, user, "captura")


def consumir_captura(db, user: User) -> dict:
    return consumir(db, user, "captura")
