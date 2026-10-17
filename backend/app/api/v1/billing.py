"""Cobro de PRO con Wompi.

Modelo: NO se usa la API de suscripciones de Wompi. El enlace recurrente se crea
una vez en su dashboard y la app solo ESCUCHA. Cada mes Wompi cobra, manda un
webhook `transaction.updated` con estado APPROVED, y aqui se extiende el
vencimiento 30 dias.

Por que ese camino y no el otro: es el unico que se puede verificar de verdad con
un enlace de pago y un webhook documentados, y degrada bien. Si Wompi deja de
cobrar porque la tarjeta fallo, simplemente no llega APPROVED y el plan vence
solo. Si se hubiera guardado "el usuario es PRO" por optimismo en el checkout,
ese usuario tendria acceso gratis para siempre.

`users.plan` sigue siendo la fuente de verdad para el resto de la app ( eso la
consume `require_plan`). Esta tabla es el historial y los dos se escriben juntos
en `_activar`.
"""
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.plan import config_plan, es_pro, plan_efectivo
from app.models.billing import Suscripcion
from app.models.user import User
from app.services import wompi

router = APIRouter(tags=["billing"])

# Lo que PRO compra. Vive aqui para que la pantalla de venta no invente la lista
# y se desincronice de core/plan.py.
QUE_INCLUYE = [
    {"titulo": "Informe en PDF", "detalle": "Listo para entregar o imprimir, mes a mes."},
    {"titulo": "Reportes detallados",
     "detalle": "Fijos contra variables, calendario de gastos y comparativas."},
    {"titulo": "Asesor sin límites",
     "detalle": "Preguntas ilimitadas sobre tus números, no cinco al día."},
    {"titulo": "Captura sin cupo diario",
     "detalle": "Escribir y dictar movimientos sin techo de quince al día."},
]

GRATIS_SIEMPRE = [
    {"titulo": "Tus datos son tuyos", "detalle": "Excel y JSON, gratis y siempre."},
    {"titulo": "Registrar, presupuestos y metas", "detalle": "Sin candado."},
]


def _suscripcion_de(db: Session, user_id: str) -> Suscripcion | None:
    return (
        db.query(Suscripcion)
        .filter_by(user_id=user_id)
        .order_by(Suscripcion.creado.desc())
        .first()
    )


def _cobro_habilitado() -> bool:
    return bool(settings.wompi_enlace_pro and settings.wompi_events_secret)


def _dias() -> int:
    return max(int(settings.pro_dias_periodo or 30), 1)


class SalirIn(BaseModel):
    motivo: str | None = None


# ---------- lo que ve el usuario ----------


@router.get("/billing/plan")
def ver_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Qué cuesta PRO, qué trae y si este usuario ya lo tiene."""
    s = _suscripcion_de(db, user.id)
    cfg = config_plan(user)
    return {
        "etiqueta": "PRO",
        "precio_mes": settings.pro_precio_mes,
        "moneda": user.moneda,
        "habilitado": _cobro_habilitado(),
        "es_pro": es_pro(user),
        "plan": plan_efectivo(user),
        "vence": s.vence.isoformat() if s and s.vence else None,
        "estado": s.estado if s else None,
        "incluye": QUE_INCLUYE,
        "gratis": GRATIS_SIEMPRE,
        "tu_plan": {"asesor_dia": cfg.get("asesor_dia"),
                    "captura_dia": cfg.get("captura_dia")},
    }


@router.post("/billing/checkout")
def checkout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Registra el intento y devuelve la URL de Wompi a la que redirigir."""
    if not _cobro_habilitado():
        raise HTTPException(503, "El cobro todavía no está configurado.")
    if es_pro(user):
        raise HTTPException(409, "Ya tienes PRO.")

    ref = wompi.referencia_nueva(f"ctd{user.id[:6]}")
    s = Suscripcion(id=str(uuid.uuid4()), user_id=user.id, estado="pendiente",
                    referencia=ref, monto=settings.pro_precio_mes)
    db.add(s)
    db.commit()

    # El enlace recurrente es UNO solo (el del dashboard). Lo que cambia por
    # usuario es la referencia, que es lo que permite saber de quién es cada
    # webhook.
    sep = "&" if "?" in settings.wompi_enlace_pro else "?"
    return {"url": f"{settings.wompi_enlace_pro}{sep}ref={ref}", "referencia": ref}


@router.post("/billing/cancelar")
def cancelar(_body: SalirIn | None = None, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """Cancela la renovación. NO corta el acceso al instante.

    El usuario ya pagó el mes que viene; cortarle ahora sería quitarle lo que
    compró. Se marca `cancela` y `vence` se queda: el acceso termina cuando
    acaba el periodo, no antes.
    """
    s = _suscripcion_de(db, user.id)
    if not s or s.estado == "cancelada":
        return {"ok": True, "estado": s.estado if s else None, "vence": None}
    s.estado = "cancelada"
    s.cancela = date.today()
    db.commit()
    return {"ok": True, "estado": s.estado,
            "vence": s.vence.isoformat() if s.vence else None}


# ---------- lo que habla con Wompi ----------


def _activar(db: Session, user: User, ref: str, monto: int, evento: str) -> dict:
    """Activa o renueva PRO. Idempotente por referencia de Wompi.

    Wompi reintenta la entrega del webhook. Sin este control, un reintento
    sumaría 30 días cada vez y el usuario pagaría un mes y tendría tres.
    """
    s = db.query(Suscripcion).filter_by(referencia=ref).first()
    if s is None:
        # Cobro sin intento registrado: se acepta, pero queda traza, porque
        # puede ser un pago legítimo con la base reiniciada.
        s = Suscripcion(id=str(uuid.uuid4()), user_id=user.id, referencia=ref)
        db.add(s)
    elif s.wompi_reference and s.estado in ("activa", "cancelada"):
        return {"ok": True, "duplicado": True}

    hoy = date.today()
    # Renovar desde `vence` si hay periodo por delante; si ya venció, desde hoy.
    # Sin esto, pagar el día 28 regalaría dos días.
    base = s.vence if (s.vence and s.vence > hoy) else hoy
    s.inicia = s.inicia or hoy
    s.vence = base + timedelta(days=_dias())
    s.estado = "activa"
    s.cancela = None
    s.monto = monto
    s.wompi_reference = ref
    s.ultimo_evento = evento
    s.user_id = user.id

    user.plan = "pro"
    user.plan_desde = s.inicia
    user.plan_vencimiento = s.vence
    db.commit()
    return {"ok": True, "vence": s.vence.isoformat()}


@router.post("/billing/webhook")
async def webhook(request: Request, db: Session = Depends(get_db),
                  x_event_checksum: str | None = Header(default=None, alias="X-Event-Checksum")):
    """Recibe los eventos de Wompi.

    No lleva autenticación propia: la autenticidad la prueba la firma, que es lo
    único que importa aquí. Sin ella, cualquiera que conozca la URL se activaría
    PRO a sí mismo.

    Un evento que no se puede verificar responde 200 igual y NO se procesa: un
    403 haría que Wompi reintentara para siempre un payload que jamás vamos a
    aceptar.

    Es `async` a proposito: `request.json()` es una corrutina. Si se usara
    `json.loads(request.body())` sin `await`, la excepcion se tragaria en el
    except, el webhook responderia 200 por siempre y NUNCA activaria PRO: la
    gente pagaria y no entraria, sin ninguna senal de error.
    """
    try:
        evento = await request.json()
    except Exception:
        return {"ok": True}
    if not isinstance(evento, dict):
        return {"ok": True}

    if not settings.wompi_events_secret:
        # Sin secreto no hay nada que verificar, así que no se toca ningún plan.
        # Es la configuración por defecto en desarrollo.
        return {"ok": True}
    if not wompi.firma_valida(evento, settings.wompi_events_secret, x_event_checksum):
        return {"ok": True}
    if not wompi.es_transaccion(evento):
        return {"ok": True}

    d = wompi.datos_transaccion(evento)
    if not wompi.es_aprobada(evento):
        # DECLINED/ERROR no reactiva nada; se deja el estado como está.
        return {"ok": True, "estado": "rechazado"}

    ref = wompi.referencia(d)
    s = db.query(Suscripcion).filter_by(referencia=ref).first()
    user = db.get(User, s.user_id) if s else None
    if user is None:
        # Referencia que no es nuestra: se ignora sin romper nada.
        return {"ok": True, "estado": "sin-suscripcion"}

    return _activar(db, user, ref, wompi.monto_centavos(d), str(evento.get("event")))