from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.models.perfil import Perfil
from app.models.finance import Account, Budget, Category, PaymentMethod, Transaction
from app.models.goals import Goal, GoalAporte
from app.models.user import User
from app.schemas.finance import CategoriaIn, CategoriaPatch

router = APIRouter(tags=["catalogos"])


# ---- Categorías RN-04 ----
@router.get("/categorias")
def listar_cats(tipo: str | None = None, solo_activas: bool = True,
                db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    q = db.query(Category).filter_by(user_id=user.id)
    if tipo:
        q = q.filter(Category.tipo == tipo)
    if solo_activas:
        q = q.filter(Category.activa.is_(True))
    return [{"id": c.id, "nombre": c.nombre, "tipo": c.tipo, "icono": c.icono, "activa": c.activa} for c in q.all()]


@router.post("/categorias", status_code=201)
def crear_cat(data: CategoriaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    if db.query(Category).filter_by(user_id=user.id, nombre=data.nombre, tipo=data.tipo).first():
        raise HTTPException(409, "Ya existe esa categoría")
    c = Category(user_id=user.id, perfil_id=perfil.id, **data.model_dump())
    db.add(c)
    db.commit()
    return {"id": c.id}


@router.patch("/categorias/{cat_id}")
def patch_cat(cat_id: str, data: CategoriaPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    c = db.query(Category).filter_by(id=cat_id, user_id=user.id).first()
    if not c:
        raise HTTPException(404, "Categoría no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    return {"id": c.id}


@router.delete("/categorias/{cat_id}", status_code=204)
def del_cat(cat_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    c = db.query(Category).filter_by(id=cat_id, user_id=user.id).first()
    if not c:
        raise HTTPException(404, "Categoría no encontrada")
    if db.query(Transaction).filter_by(categoria_id=cat_id).count() > 0:
        raise HTTPException(409, "Tiene movimientos: desactívala en vez de borrarla")
    db.delete(c)
    db.commit()
    return None


# ---- Métodos de pago ----
@router.get("/metodos-pago")
def listar_metodos(db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    return [{"id": m.id, "nombre": m.nombre} for m in db.query(PaymentMethod).filter_by(user_id=user.id).all()]


@router.post("/metodos-pago", status_code=201)
def crear_metodo(nombre: str = Body(..., embed=True), db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    if db.query(PaymentMethod).filter_by(user_id=user.id, nombre=nombre).first():
        raise HTTPException(409, "Ya existe ese método")
    m = PaymentMethod(user_id=user.id, nombre=nombre)
    db.add(m)
    db.commit()
    return {"id": m.id}


@router.delete("/metodos-pago/{metodo_id}", status_code=204)
def del_metodo(metodo_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    m = db.query(PaymentMethod).filter_by(id=metodo_id, user_id=user.id).first()
    if not m:
        raise HTTPException(404, "Método no encontrado")
    if db.query(Transaction).filter_by(metodo_id=metodo_id).count() > 0:
        raise HTTPException(409, "Tiene movimientos: no se puede borrar")
    db.delete(m)
    db.commit()
    return None


# ---- Respaldo MVP-10 ----
@router.get("/respaldo/export")
def export(formato: str = "json", db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    if formato not in ("json", "csv"):
        raise HTTPException(422, "formato debe ser json|csv")
    data = {
        "version": 1, "usuario": user.correo, "moneda": user.moneda,
        "cuentas": [{"id": a.id, "nombre": a.nombre, "tipo": a.tipo, "saldo_inicial": float(a.saldo_inicial)}
                    for a in db.query(Account).filter_by(user_id=user.id).all()],
        "categorias": [{"id": c.id, "nombre": c.nombre, "tipo": c.tipo, "icono": c.icono, "activa": c.activa}
                       for c in db.query(Category).filter_by(user_id=user.id).all()],
        "metodos": [{"id": m.id, "nombre": m.nombre} for m in db.query(PaymentMethod).filter_by(user_id=user.id).all()],
        "movimientos": [{"tipo": t.tipo, "monto": float(t.monto), "fecha": str(t.fecha), "descripcion": t.descripcion,
                         "cuenta_id": t.cuenta_id, "categoria_id": t.categoria_id, "metodo_id": t.metodo_id,
                         "idempotency_key": t.idempotency_key}
                        for t in db.query(Transaction).filter_by(user_id=user.id).all()],
        "presupuestos": [{"categoria_id": b.categoria_id, "monto": float(b.monto), "periodo": b.periodo}
                         for b in db.query(Budget).filter_by(user_id=user.id).all()],
        "metas": [{"nombre": g.nombre, "objetivo": float(g.objetivo),
                   "fecha_objetivo": str(g.fecha_objetivo) if g.fecha_objetivo else None,
                   "imagen_url": g.imagen_url,
                   "aportes": [{"monto": float(a.monto), "fecha": str(a.fecha)}
                               for a in db.query(GoalAporte).filter_by(goal_id=g.id).all()]}
                  for g in db.query(Goal).filter_by(user_id=user.id).all()],
    }
    if formato == "csv":
        lines = ["tipo,monto,fecha,descripcion"]
        for t in data["movimientos"]:
            lines.append(f"{t['tipo']},{t['monto']},{t['fecha']},{(t['descripcion'] or '').replace(',', ';')}")
        return {"formato": "csv", "contenido": "\n".join(lines)}
    return data


@router.post("/respaldo/import")
def import_data(payload: dict = Body(...), modo: str = Query(default="agregar", pattern="^(reemplazar|agregar)$"),
                db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    if payload.get("version") != 1:
        raise HTTPException(422, "version debe ser 1")
    creados, omitidos, errores = 0, 0, []
    if modo == "reemplazar":
        for model in (Transaction, Budget, GoalAporte, Goal, PaymentMethod, Category, Account):
            db.query(model).filter_by(user_id=user.id).delete()
        db.flush()
    # Mapas id viejo -> nuevo para cuentas/categorías/métodos
    mapa_cuentas, mapa_cats, mapa_met = {}, {}, {}
    for a in payload.get("cuentas", []):
        na = Account(user_id=user.id, perfil_id=perfil.id, nombre=a["nombre"], tipo=a.get("tipo", "otro"), saldo_inicial=a.get("saldo_inicial", 0))
        db.add(na)
        db.flush()
        if a.get("id"):
            mapa_cuentas[a["id"]] = na.id
        creados += 1
    for c in payload.get("categorias", []):
        if db.query(Category).filter_by(user_id=user.id, nombre=c["nombre"], tipo=c.get("tipo", "gasto")).first():
            omitidos += 1
            continue
        nc = Category(user_id=user.id, perfil_id=perfil.id, nombre=c["nombre"], tipo=c.get("tipo", "gasto"),
                      icono=c.get("icono", "tag"), activa=c.get("activa", True))
        db.add(nc)
        db.flush()
        if c.get("id"):
            mapa_cats[c["id"]] = nc.id
        creados += 1
    for m in payload.get("metodos", []):
        if db.query(PaymentMethod).filter_by(user_id=user.id, nombre=m["nombre"]).first():
            omitidos += 1
            continue
        nm = PaymentMethod(user_id=user.id, nombre=m["nombre"])
        db.add(nm)
        db.flush()
        if m.get("id"):
            mapa_met[m["id"]] = nm.id
        creados += 1
    for t in payload.get("movimientos", []):
        try:
            if float(t["monto"]) <= 0:
                raise ValueError("monto debe ser > 0")
            date.fromisoformat(t["fecha"])
            cid = mapa_cuentas.get(t.get("cuenta_id"), t.get("cuenta_id"))
            if not cid or not db.query(Account).filter_by(id=cid, user_id=user.id).first():
                # usa primera cuenta disponible
                primera = db.query(Account).filter_by(user_id=user.id).first()
                if not primera:
                    raise ValueError("sin cuentas para importar")
                cid = primera.id
            db.add(Transaction(user_id=user.id, perfil_id=perfil.id, tipo=t["tipo"], monto=t["monto"], fecha=t["fecha"],
                               descripcion=t.get("descripcion", ""),
                               cuenta_id=cid,
                               categoria_id=mapa_cats.get(t.get("categoria_id"), t.get("categoria_id")),
                               metodo_id=mapa_met.get(t.get("metodo_id"), t.get("metodo_id")),
                               idempotency_key=t.get("idempotency_key")))
            creados += 1
        except Exception as e:
            errores.append(str(e))
    # Presupuestos (respeta unicidad usuario+categoría+periodo)
    for b in payload.get("presupuestos", []):
        try:
            cid = mapa_cats.get(b.get("categoria_id"), b.get("categoria_id"))
            if not cid or not db.query(Category).filter_by(id=cid, user_id=user.id).first():
                raise ValueError("categoría de presupuesto no encontrada")
            if db.query(Budget).filter_by(user_id=user.id, categoria_id=cid, periodo=b["periodo"]).first():
                omitidos += 1
                continue
            db.add(Budget(user_id=user.id, perfil_id=perfil.id, categoria_id=cid, monto=b["monto"], periodo=b["periodo"]))
            creados += 1
        except Exception as e:
            errores.append(str(e))
    # Metas + aportes (Opción A: solo seguimiento, no tocan saldos)
    for g in payload.get("metas", []):
        try:
            ng = Goal(user_id=user.id, perfil_id=perfil.id, nombre=g["nombre"], objetivo=g["objetivo"],
                      fecha_objetivo=date.fromisoformat(g["fecha_objetivo"]) if g.get("fecha_objetivo") else None,
                      imagen_url=g.get("imagen_url"))
            db.add(ng)
            db.flush()
            for a in g.get("aportes", []):
                if float(a["monto"]) <= 0:
                    raise ValueError("aporte debe ser > 0")
                db.add(GoalAporte(goal_id=ng.id, user_id=user.id, monto=a["monto"], fecha=date.fromisoformat(a["fecha"])))
            creados += 1
        except Exception as e:
            errores.append(str(e))
    db.commit()
    return {"creados": creados, "omitidos_duplicados": omitidos, "errores": errores}
