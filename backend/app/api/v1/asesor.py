from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.core.plan import consumo_asesor, consumir_asesor
from app.core.ratelimit import asesor_limit
from app.models.asesor import AsesorChat, AsesorMensaje
from app.models.perfil import Perfil
from app.models.user import User
from app.services import asesor as asesor_svc

router = APIRouter(tags=["asesor"])



class AsesorIn(BaseModel):
    mensaje: str = Field(min_length=1, max_length=1000)
    mes: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    chat_id: str | None = None


def _titulo(mensaje: str) -> str:
    t = " ".join(mensaje.split())[:60]
    return t if len(mensaje) <= 60 else t + "…"


@router.get("/asesor/chats")
def listar_chats(db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    chats = db.query(AsesorChat).filter_by(user_id=user.id, perfil_id=perfil.id).order_by(AsesorChat.created_at.desc()).all()
    out = []
    for c in chats:
        n = db.query(func.count(AsesorMensaje.id)).filter_by(chat_id=c.id).scalar() or 0
        out.append({"id": c.id, "titulo": c.titulo, "mensajes": n, "created_at": str(c.created_at)})
    return out


@router.get("/asesor/chats/{chat_id}")
def obtener_chat(chat_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    c = db.query(AsesorChat).filter_by(id=chat_id, user_id=user.id, perfil_id=perfil.id).first()
    if not c:
        raise HTTPException(404, "Chat no encontrado")
    msgs = db.query(AsesorMensaje).filter_by(chat_id=chat_id).order_by(AsesorMensaje.created_at).all()
    return {"id": c.id, "titulo": c.titulo,
            "mensajes": [{"yo": m.rol == "user", "texto": m.contenido} for m in msgs]}


@router.delete("/asesor/chats/{chat_id}", status_code=204)
def borrar_chat(chat_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    c = db.query(AsesorChat).filter_by(id=chat_id, user_id=user.id, perfil_id=perfil.id).first()
    if not c:
        raise HTTPException(404, "Chat no encontrado")
    db.query(AsesorMensaje).filter_by(chat_id=chat_id).delete()
    db.delete(c)
    db.commit()
    return None


@router.get("/asesor/uso")
def uso_asesor(db: Session = Depends(get_db), user: User = Depends(get_current_user),
               perfil: Perfil = Depends(get_perfil)):
    """Consumo de hoy, para pintar 'te quedan N' en la UI sin adivinar."""
    return consumo_asesor(db, user)


@router.get("/asesor/revision")
def revision(db: Session = Depends(get_db), user: User = Depends(get_current_user),
             perfil: Perfil = Depends(get_perfil), fecha: str | None = None):
    """Como vas en la quincena y que se viene encima.

    Sin push ni cron: se calcula al abrir la app. Por que es suficiente: la
    quincena dura 15 dias y el usuario abre la app varias veces al dia, asi que la
    informacion esta lista cuando se necesita, sin infraestructura de recordatorios.
    """
    from app.services.quincena import revision as revisar

    f = None
    if fecha:
        try:
            f = date.fromisoformat(fecha)
        except ValueError:
            raise HTTPException(422, "fecha debe ser YYYY-MM-DD")
    return revisar(db, user.id, perfil.id, f)


@router.post("/asesor/chat", dependencies=[Depends(asesor_limit)])
def chat(data: AsesorIn, db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
        perfil: Perfil = Depends(get_perfil)):
    from datetime import date

    # Cuota por usuario y plan (Redis, con fallback a Postgres). El advisor_limit por
    # IP sigue puesto como red de seguridad, no como cuota comercial.
    cuota = consumir_asesor(db, user)
    mes = data.mes or date.today().strftime("%Y-%m")
    if data.chat_id:
        c = db.query(AsesorChat).filter_by(id=data.chat_id, user_id=user.id, perfil_id=perfil.id).first()
        if not c:
            raise HTTPException(404, "Chat no encontrado")
    else:
        c = AsesorChat(user_id=user.id, perfil_id=perfil.id, titulo=_titulo(data.mensaje))
        db.add(c)
        db.flush()
    # Continuidad: los ultimos turnos se replayan como mensajes reales (user/assistant),
    # no aplastados a texto plano, para que el modelo respete el hilo.
    previos = db.query(AsesorMensaje).filter_by(chat_id=c.id).order_by(
        AsesorMensaje.created_at.desc()).limit(8).all()
    db.add(AsesorMensaje(chat_id=c.id, user_id=user.id, rol="user", contenido=data.mensaje))
    db.flush()
    ctx = asesor_svc.contexto(db, user.id, perfil.id, mes, user.moneda)
    try:
        respuesta, tokens = asesor_svc.preguntar(
            data.mensaje, ctx, db=db, user_id=user.id, perfil_id=perfil.id, mes=mes,
            historial=list(reversed(previos)))
    except RuntimeError as e:
        db.rollback()
        code = 503 if "no configurado" in str(e) else 502
        raise HTTPException(status_code=code, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=502, detail="El asesor falló. Intenta de nuevo.")
    db.add(AsesorMensaje(chat_id=c.id, user_id=user.id, rol="assistant", contenido=respuesta, tokens=tokens))
    db.commit()
    cuota["queda"] = max(cuota["queda"] - 1, 0)
    return {"respuesta": respuesta, "tokens": tokens, "mes": mes, "chat_id": c.id, "cuota": cuota}
