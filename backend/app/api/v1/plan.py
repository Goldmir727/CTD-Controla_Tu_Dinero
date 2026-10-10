from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.models.perfil import Perfil
from app.models.finance import Budget, Category, Transaction
from app.models.goals import Goal, GoalAporte
from app.models.user import User
from app.schemas.finance import PresupuestoIn, PresupuestoPatch
from app.schemas.goals import AporteIn, MetaIn, MetaOut, MetaPatch
from app.services.calculos import (
    ahorro_requerido_mensual,
    meta_excedente,
    meta_faltante,
    meta_porcentaje,
    meses_restantes,
    presupuesto_estado,
    presupuesto_porcentaje,
    presupuesto_restante,
)

router = APIRouter(tags=["plan"])


# ---- Presupuestos RC-03 ----
@router.post("/presupuestos", status_code=201)
def crear_presupuesto(data: PresupuestoIn, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    cat = db.query(Category).filter_by(id=data.categoria_id, user_id=user.id, perfil_id=perfil.id).first()
    if not cat:
        raise HTTPException(404, "Categoría no encontrada")
    if cat.tipo not in ("gasto", "ambos"):
        raise HTTPException(422, f"La categoría {cat.nombre} es de ingreso: no admite presupuesto")
    if db.query(Budget).filter_by(user_id=user.id, perfil_id=perfil.id,
                                                    categoria_id=data.categoria_id, periodo=data.periodo).first():
        raise HTTPException(409, "Ya existe presupuesto para esa categoría y periodo")
    b = Budget(user_id=user.id, perfil_id=perfil.id, **data.model_dump())
    db.add(b)
    db.commit()
    return {"id": b.id}


@router.get("/presupuestos")
def listar_presupuestos(periodo: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    from app.services import colombia as co

    hoy = date.today()
    ultimo = co.dias_del_mes(periodo)
    # Un mes futuro no tiene dias transcurridos que contar.
    transcurridos = min(hoy.day, ultimo) if periodo == hoy.strftime("%Y-%m") else 0
    out = []
    for b in db.query(Budget).filter_by(user_id=user.id, perfil_id=perfil.id,
                          periodo=periodo).all():
        gastado = db.query(func.coalesce(func.sum(Transaction.monto), 0)).filter(
            Transaction.user_id == user.id, Transaction.perfil_id == perfil.id, Transaction.categoria_id == b.categoria_id,
            Transaction.tipo == "gasto", func.to_char(Transaction.fecha, "YYYY-MM") == periodo,
        ).scalar() or 0
        gastado = float(gastado)
        monto = float(b.monto)
        pct = presupuesto_porcentaje(monto, gastado)
        cat = db.get(Category, b.categoria_id)
        ritmo = round(gastado / transcurridos, 2) if transcurridos else 0.0
        sostenible = round(monto / ultimo, 2) if ultimo else 0.0
        esperado = round(sostenible * transcurridos, 2)
        fila = {"id": b.id, "categoria_id": b.categoria_id, "categoria": cat.nombre if cat else "",
                "monto": monto, "periodo": periodo, "gastado": gastado,
                "restante": presupuesto_restante(monto, gastado), "porcentaje_uso": pct,
                "estado": presupuesto_estado(pct),
                # Lo que faltaba del contrato §6: sin esto la UI no puede decir
                # "llevas 80% el día 12", que es el aviso que de verdad ayuda.
                "ritmo_diario": ritmo, "ritmo_sostenible": sostenible,
                "dias_transcurridos": transcurridos, "dias_periodo": ultimo,
                "gastado_esperado": esperado,
                "delta_puntos": round(pct - (transcurridos / ultimo * 100), 1) if ultimo else 0.0}
        if restante_ok(fila, restante=presupuesto_restante(monto, gastado)):
            fila["mensaje"] = mensaje_presupuesto(fila)
        out.append(fila)
    return out


def restante_ok(fila: dict, restante: float) -> bool:
    return restante < 0 or (fila["delta_puntos"] >= 20 and fila["porcentaje_uso"] >= 80)


def mensaje_presupuesto(f: dict) -> str:
    cat = f["categoria"] or "esa categoría"
    dias, total = f["dias_transcurridos"], f["dias_periodo"]
    if f["porcentaje_uso"] > 100:
        return (f"Te pasaste {f['porcentaje_uso'] - 100:.0f} puntos en {cat} "
                f"y solo llevas {dias} de {total} días.")
    faltantes = total - dias
    return (f"Llevas el {f['porcentaje_uso']:.0f}% de {cat} con {dias} de {total} días: "
            f"vas {f['delta_puntos']:.0f} puntos por encima del ritmo. A "
            f"{dinero(f['ritmo_diario'])} no alcanzas, lo sostenible sería {dinero(f['ritmo_sostenible'])}."
            + (f" Ajusta los últimos {faltantes} días." if faltantes > 0
               else " Ya no queda mes para corregirlo."))


@router.patch("/presupuestos/{pres_id}")
def actualizar_presupuesto(pres_id: str, data: PresupuestoPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    b = db.query(Budget).filter_by(id=pres_id, user_id=user.id, perfil_id=perfil.id).first()
    if not b:
        raise HTTPException(404, "Presupuesto no encontrado")
    b.monto = data.monto
    db.commit()
    return {"id": b.id, "monto": float(b.monto)}


@router.delete("/presupuestos/{pres_id}", status_code=204)
def eliminar_presupuesto(pres_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    b = db.query(Budget).filter_by(id=pres_id, user_id=user.id, perfil_id=perfil.id).first()
    if not b:
        raise HTTPException(404, "Presupuesto no encontrado")
    db.delete(b)
    db.commit()
    return None


# ---- Metas RC-04/RC-05, RN-09 Opción A ----
from app.services.imagenes import validar_imagen as _validar_imagen_url
# El aviso de presupuesto lo lee el usuario en la pantalla: con el formato ingles
# "1,301,667" lo leeria distinto a como la app muestra los $1.301.667 de al lado.
from app.services.formato import dinero

MAX_IMAGEN_CHARS = 700_000  # ~500KB en base64


def _validar_imagen(imagen_url: str | None) -> None:
    _validar_imagen_url(imagen_url, MAX_IMAGEN_CHARS)


def _meta_out(db: Session, g: Goal, hoy: date) -> MetaOut:
    ahorrado = float(db.query(func.coalesce(func.sum(GoalAporte.monto), 0)).filter_by(goal_id=g.id).scalar() or 0)
    objetivo = float(g.objetivo)
    falt = meta_faltante(objetivo, ahorrado)
    meses = meses_restantes(g.fecha_objetivo, hoy)
    vencida = bool(g.fecha_objetivo and g.fecha_objetivo < hoy and falt > 0)
    return MetaOut(id=g.id, nombre=g.nombre, objetivo=objetivo, ahorrado=ahorrado, faltante=falt,
                   porcentaje=meta_porcentaje(objetivo, ahorrado), excedente=meta_excedente(objetivo, ahorrado),
                   meses_restantes=meses, ahorro_requerido_mensual=ahorro_requerido_mensual(falt, meses),
                   estado="completada" if ahorrado >= objetivo else "en_curso", vencida=vencida,
                   imagen_url=g.imagen_url)


@router.post("/metas", status_code=201)
def crear_meta(data: MetaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    _validar_imagen(data.imagen_url)
    g = Goal(user_id=user.id, perfil_id=perfil.id, **data.model_dump())
    db.add(g)
    db.commit()
    return {"id": g.id}


@router.get("/metas", response_model=list[MetaOut])
def listar_metas(db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    return [_meta_out(db, g, date.today()) for g in
            db.query(Goal).filter_by(user_id=user.id, perfil_id=perfil.id).all()]


@router.post("/metas/{goal_id}/aportes", status_code=201)
def aportar(goal_id: str, data: AporteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user),
            perfil: Perfil = Depends(get_perfil),
            idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    g = db.query(Goal).filter_by(id=goal_id, user_id=user.id, perfil_id=perfil.id).first()
    if not g:
        raise HTTPException(404, "Meta no encontrada")
    if idempotency_key and db.query(GoalAporte).filter_by(user_id=user.id, idempotency_key=idempotency_key).first():
        raise HTTPException(409, "Aporte duplicado (Idempotency-Key)")
    # GoalAporte no lleva perfil_id: hereda el de la meta, asi que un aporte nunca
    # puede quedar en un perfil distinto al de su meta.
    ap = GoalAporte(goal_id=goal_id, user_id=user.id, monto=data.monto,
                    fecha=data.fecha or date.today(), idempotency_key=idempotency_key)
    db.add(ap)
    db.commit()
    # RN-09: NO toca cuentas ni movimientos.
    return {"ok": True}


@router.get("/metas/{goal_id}/aportes")
def listar_aportes(goal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    g = db.query(Goal).filter_by(id=goal_id, user_id=user.id, perfil_id=perfil.id).first()
    if not g:
        raise HTTPException(404, "Meta no encontrada")
    return [{"id": a.id, "monto": float(a.monto), "fecha": str(a.fecha)}
            for a in db.query(GoalAporte).filter_by(goal_id=goal_id).order_by(GoalAporte.fecha.desc()).all()]


@router.delete("/metas/{goal_id}/aportes/{aporte_id}", status_code=204)
def eliminar_aporte(goal_id: str, aporte_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    a = db.query(GoalAporte).filter_by(id=aporte_id, goal_id=goal_id, user_id=user.id).first()
    if not a:
        raise HTTPException(404, "Aporte no encontrado")
    db.delete(a)
    db.commit()
    return None


@router.patch("/metas/{goal_id}")
def actualizar_meta(goal_id: str, data: MetaPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    g = db.query(Goal).filter_by(id=goal_id, user_id=user.id, perfil_id=perfil.id).first()
    if not g:
        raise HTTPException(404, "Meta no encontrada")
    patch = data.model_dump(exclude_unset=True)
    if "imagen_url" in patch:
        _validar_imagen(patch["imagen_url"])
        g.imagen_url = patch.pop("imagen_url") or None
    for k, v in patch.items():
        setattr(g, k, v)
    db.commit()
    return {"id": g.id}


@router.delete("/metas/{goal_id}", status_code=204)
def eliminar_meta(goal_id: str, confirm: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    if not confirm:
        raise HTTPException(422, "Confirma con ?confirm=true")
    g = db.query(Goal).filter_by(id=goal_id, user_id=user.id, perfil_id=perfil.id).first()
    if not g:
        raise HTTPException(404, "Meta no encontrada")
    db.query(GoalAporte).filter_by(goal_id=goal_id).delete()
    db.delete(g)
    db.commit()
    return None
