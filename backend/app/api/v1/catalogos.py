from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.models.perfil import Perfil
from app.models.finance import Account, Budget, Category, PaymentMethod, Transaction
from app.models.goals import Goal, GoalAporte, Recurring
from app.models.user import User
from app.schemas.finance import CategoriaIn, CategoriaPatch

router = APIRouter(tags=["catalogos"])


# ---- Categorías RN-04 ----
@router.get("/categorias")
def listar_cats(tipo: str | None = None, solo_activas: bool = True,
                db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    q = db.query(Category).filter_by(user_id=user.id, perfil_id=perfil.id)
    if tipo:
        q = q.filter(Category.tipo == tipo)
    if solo_activas:
        q = q.filter(Category.activa.is_(True))
    return [{"id": c.id, "nombre": c.nombre, "tipo": c.tipo, "icono": c.icono, "activa": c.activa} for c in q.all()]


@router.post("/categorias", status_code=201)
def crear_cat(data: CategoriaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    if db.query(Category).filter_by(user_id=user.id, perfil_id=perfil.id,
                                             nombre=data.nombre, tipo=data.tipo).first():
        raise HTTPException(409, "Ya existe esa categoría")
    c = Category(user_id=user.id, perfil_id=perfil.id, **data.model_dump())
    db.add(c)
    db.commit()
    return {"id": c.id}


@router.patch("/categorias/{cat_id}")
def patch_cat(cat_id: str, data: CategoriaPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    c = db.query(Category).filter_by(id=cat_id, user_id=user.id, perfil_id=perfil.id).first()
    if not c:
        raise HTTPException(404, "Categoría no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    return {"id": c.id}


@router.delete("/categorias/{cat_id}", status_code=204)
def del_cat(cat_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    c = db.query(Category).filter_by(id=cat_id, user_id=user.id, perfil_id=perfil.id).first()
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
def export(formato: str = "json", db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    """Respaldo COMPLETO del usuario, de TODOS sus perfiles.

    A proposito ignora el perfil activo: un respaldo que solo sacara el Negocio
    perderia el Personal, y al reimportar en una cuenta limpia el usuario tendria
    que adivinar que le falta una mitad. Cada fila lleva el nombre de su perfil.
    """
    if formato not in ("json", "csv"):
        raise HTTPException(422, "formato debe ser json|csv")
    perfiles = {p.id: p.nombre for p in db.query(Perfil).filter_by(user_id=user.id).all()}
    data = {
        "version": 2, "usuario": user.correo, "moneda": user.moneda,
        "perfiles": [{"id": p.id, "nombre": p.nombre, "tipo": p.tipo, "principal": p.principal}
                    for p in db.query(Perfil).filter_by(user_id=user.id).all()],
        "cuentas": [{"id": a.id, "perfil": perfiles.get(a.perfil_id), "nombre": a.nombre,
                     "tipo": a.tipo, "saldo_inicial": float(a.saldo_inicial)}
                    for a in db.query(Account).filter_by(user_id=user.id).all()],
        "categorias": [{"id": c.id, "perfil": perfiles.get(c.perfil_id), "nombre": c.nombre,
                        "tipo": c.tipo, "icono": c.icono, "activa": c.activa}
                       for c in db.query(Category).filter_by(user_id=user.id).all()],
        "metodos": [{"id": m.id, "nombre": m.nombre} for m in db.query(PaymentMethod).filter_by(user_id=user.id).all()],
        "movimientos": [{"perfil": perfiles.get(t.perfil_id), "tipo": t.tipo, "monto": float(t.monto),
                         "fecha": str(t.fecha), "descripcion": t.descripcion,
                         "cuenta_id": t.cuenta_id, "categoria_id": t.categoria_id, "metodo_id": t.metodo_id,
                         "idempotency_key": t.idempotency_key}
                        for t in db.query(Transaction).filter_by(user_id=user.id).all()],
        "presupuestos": [{"perfil": perfiles.get(b.perfil_id), "categoria_id": b.categoria_id,
                          "monto": float(b.monto), "periodo": b.periodo}
                         for b in db.query(Budget).filter_by(user_id=user.id).all()],
        "recurrentes": [{"perfil": perfiles.get(r.perfil_id), "nombre": r.nombre, "tipo": r.tipo,
                         "monto": float(r.monto), "dia": r.dia, "frecuencia": r.frecuencia,
                         "activo": r.activo}
                        for r in db.query(Recurring).filter_by(user_id=user.id).all()],
        "metas": [{"perfil": perfiles.get(g.perfil_id), "nombre": g.nombre, "objetivo": float(g.objetivo),
                   "fecha_objetivo": str(g.fecha_objetivo) if g.fecha_objetivo else None,
                   "imagen_url": g.imagen_url,
                   "aportes": [{"monto": float(a.monto), "fecha": str(a.fecha)}
                               for a in db.query(GoalAporte).filter_by(goal_id=g.id).all()]}
                  for g in db.query(Goal).filter_by(user_id=user.id).all()],
    }
    if formato == "csv":
        lines = ["perfil,tipo,monto,fecha,descripcion"]
        for t in data["movimientos"]:
            desc = (t["descripcion"] or "").replace(",", ";")
            lines.append(f"{t['perfil']},{t['tipo']},{t['monto']},{t['fecha']},{desc}")
        return {"formato": "csv", "contenido": "\n".join(lines)}
    return data


@router.post("/respaldo/import")
def import_data(payload: dict = Body(...), modo: str = Query(default="agregar", pattern="^(reemplazar|agregar)$"),
                db: Session = Depends(get_db), user: User = Depends(get_current_user),
                perfil: Perfil = Depends(get_perfil)):
    """Restaura un respaldo, creando los perfiles que vengan en el archivo.

    Cada fila del respaldo trae el NOMBRE de su perfil. Se crea el perfil si no
    existe y todo se cuelga de él: si no, el Negocio terminaria mezclado con el
    Personal, que es justo lo que el modulo de perfiles evita.
    """
    version = payload.get("version")
    if version not in (1, 2):
        raise HTTPException(422, "version debe ser 1 o 2")
    creados, omitidos, errores = 0, 0, []
    if modo == "reemplazar":
        for model in (Transaction, Budget, GoalAporte, Goal, Recurring, PaymentMethod, Category, Account):
            db.query(model).filter_by(user_id=user.id).delete()
        db.flush()
        # Los perfiles se recrean desde cero en modo reemplazar.
        for p in db.query(Perfil).filter_by(user_id=user.id).all():
            if not p.principal:
                db.delete(p)
        db.flush()

    # Perfiles: los del respaldo, o el activo si el archivo es v1.
    perfil_por_nombre = {p.nombre: p for p in db.query(Perfil).filter_by(user_id=user.id).all()}
    for pd in payload.get("perfiles", []):
        nombre = pd.get("nombre") or "Perfil"
        if nombre in perfil_por_nombre:
            continue
        nuevo = Perfil(user_id=user.id, nombre=nombre, tipo=pd.get("tipo", "personal"),
                       principal=False, notificar_mezcla=True)
        db.add(nuevo)
        db.flush()
        perfil_por_nombre[nombre] = nuevo
        creados += 1

    def _perfil_de(fila: dict) -> Perfil:
        """Resuelve el perfil de una fila por nombre; si no viene, cae al activo."""
        nombre = fila.get("perfil")
        if nombre and nombre in perfil_por_nombre:
            return perfil_por_nombre[nombre]
        if nombre and nombre not in perfil_por_nombre:
            nuevo = Perfil(user_id=user.id, nombre=nombre, tipo="personal", principal=False)
            db.add(nuevo)
            db.flush()
            perfil_por_nombre[nombre] = nuevo
        return perfil_por_nombre.get(perfil.nombre, perfil)

    # Mapas id viejo -> nuevo para cuentas/categorías/métodos
    mapa_cuentas, mapa_cats, mapa_met = {}, {}, {}
    for a in payload.get("cuentas", []):
        na = Account(user_id=user.id, perfil_id=_perfil_de(a).id, nombre=a["nombre"],
                     tipo=a.get("tipo", "otro"), saldo_inicial=a.get("saldo_inicial", 0))
        db.add(na)
        db.flush()
        if a.get("id"):
            mapa_cuentas[a["id"]] = na.id
        creados += 1
    for c in payload.get("categorias", []):
        destino = _perfil_de(c)
        if db.query(Category).filter_by(user_id=user.id, perfil_id=destino.id,
                                        nombre=c["nombre"], tipo=c.get("tipo", "gasto")).first():
            omitidos += 1
            continue
        nc = Category(user_id=user.id, perfil_id=destino.id, nombre=c["nombre"],
                      tipo=c.get("tipo", "gasto"),
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
            destino = _perfil_de(t)
            cid = mapa_cuentas.get(t.get("cuenta_id"), t.get("cuenta_id"))
            # La cuenta debe existir Y ser del mismo perfil del movimiento: si no,
            # el respaldo cruzaria Personal y Negocio.
            if not cid or not db.query(Account).filter_by(id=cid, user_id=user.id,
                                                          perfil_id=destino.id).first():
                primera = db.query(Account).filter_by(user_id=user.id,
                                                      perfil_id=destino.id).first()
                if not primera:
                    raise ValueError(f"sin cuentas para importar en el perfil {destino.nombre}")
                cid = primera.id
            cat_id = mapa_cats.get(t.get("categoria_id"), t.get("categoria_id"))
            if cat_id and not db.query(Category).filter_by(id=cat_id, user_id=user.id,
                                                           perfil_id=destino.id).first():
                cat_id = None
            met_id = mapa_met.get(t.get("metodo_id"), t.get("metodo_id"))
            if met_id and not db.query(PaymentMethod).filter_by(id=met_id, user_id=user.id).first():
                met_id = None
            db.add(Transaction(user_id=user.id, perfil_id=destino.id, tipo=t["tipo"],
                               monto=t["monto"], fecha=t["fecha"],
                               descripcion=t.get("descripcion", ""),
                               cuenta_id=cid, categoria_id=cat_id, metodo_id=met_id,
                               idempotency_key=t.get("idempotency_key")))
            creados += 1
        except Exception as e:
            errores.append(str(e))
    # Presupuestos (respeta unicidad perfil+categoría+periodo)
    for b in payload.get("presupuestos", []):
        try:
            destino = _perfil_de(b)
            cid = mapa_cats.get(b.get("categoria_id"), b.get("categoria_id"))
            if not cid or not db.query(Category).filter_by(id=cid, user_id=user.id,
                                                           perfil_id=destino.id).first():
                raise ValueError("categoría de presupuesto no encontrada")
            if db.query(Budget).filter_by(perfil_id=destino.id, categoria_id=cid,
                                          periodo=b["periodo"]).first():
                omitidos += 1
                continue
            db.add(Budget(user_id=user.id, perfil_id=destino.id, categoria_id=cid,
                          monto=b["monto"], periodo=b["periodo"]))
            creados += 1
        except Exception as e:
            errores.append(str(e))
    # Ingresos y gastos fijos declarativos
    for r in payload.get("recurrentes", []):
        try:
            destino = _perfil_de(r)
            db.add(Recurring(user_id=user.id, perfil_id=destino.id, nombre=r["nombre"],
                             tipo=r.get("tipo", "gasto"), monto=r["monto"],
                             dia=r.get("dia", 1), frecuencia=r.get("frecuencia", "mensual"),
                             activo=r.get("activo", True)))
            creados += 1
        except Exception as e:
            errores.append(str(e))
    # Metas + aportes (Opción A: solo seguimiento, no tocan saldos)
    for g in payload.get("metas", []):
        try:
            destino = _perfil_de(g)
            ng = Goal(user_id=user.id, perfil_id=destino.id, nombre=g["nombre"], objetivo=g["objetivo"],
                      fecha_objetivo=date.fromisoformat(g["fecha_objetivo"]) if g.get("fecha_objetivo") else None,
                      imagen_url=g.get("imagen_url"))
            db.add(ng)
            db.flush()
            for a in g.get("aportes", []):
                if float(a["monto"]) <= 0:
                    raise ValueError("aporte debe ser > 0")
                db.add(GoalAporte(goal_id=ng.id, user_id=user.id, monto=a["monto"],
                                  fecha=date.fromisoformat(a["fecha"])))
            creados += 1
        except Exception as e:
            errores.append(str(e))
    db.commit()
    return {"creados": creados, "omitidos_duplicados": omitidos, "errores": errores}
