
"""Propuesta y confirmacion de capturas: la logica que la web y el bot comparten.

Por que NO vive en el endpoint: hay DOS puertas que necesitan exactamente lo
mismo, la PWA y el bot de WhatsApp. Copiarlo era la via directa a que el bot
terminara guardando los movimientos un pelo distinto que la web, y a que una
correccion en una se olvidara en la otra.

No lanza HTTPException: aqui se reportan los problemas por movimiento y se sigue.
Quien llama decide si eso es un error o un aviso.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.models.finance import Account, Category, PaymentMethod, Transaction
from app.services import captura as cap

__all__ = ["proponer", "confirmar_captura", "validar_fecha", "resolver_cuenta"]


def validar_fecha(iso: str) -> date:
    from datetime import timedelta

    try:
        f = date.fromisoformat(iso)
    except (ValueError, TypeError):
        raise ValueError("Fecha inválida")
    if f > date.today() + timedelta(days=1):
        raise ValueError("La fecha no puede ser más de 1 día en el futuro")
    return f


def resolver_cuenta(db: Session, perfil_id: str, cuenta_id: str | None) -> Account | None:
    if cuenta_id:
        c = db.query(Account).filter_by(id=cuenta_id, perfil_id=perfil_id).first()
        if c:
            return c
        raise ValueError("Esa cuenta no existe en este perfil")
    return db.query(Account).filter_by(perfil_id=perfil_id).order_by(Account.nombre).first()


def proponer(db: Session, user, perfil, texto: str,
             transcripcion: str | None = None) -> dict:
    """Analiza una frase y devuelve la propuesta YA PERSISTIDA, con las
    coincidencias de fijos resueltas.

    Vive en el servicio, no en el endpoint, porque el bot de WhatsApp la necesita
    exactamente igual que la web: misma interpretacion, misma bitacora, misma
    pregunta de "¿este es tu Arriendo?". Si cada canal armara la propuesta por
    su cuenta, los dos acabarian interpretando distinto la misma frase.
    """
    import json as _json

    from app.models.captura import Captura
    from app.services import deteccion as det

    p = cap.analizar(texto, db, user.id, perfil.id)

    reg = Captura(user_id=user.id, perfil_id=perfil.id, texto=texto,
                  transcripcion=transcripcion, estado="propuesta",
                  propuestos=_json.dumps(p["movimientos"], default=str),
                  monto_dudoso=p["requiere_confirmacion_monto"])
    db.add(reg)
    db.commit()
    db.refresh(reg)

    for m in p["movimientos"]:
        fecha = validar_fecha(m["fecha"])
        m["coincidencias"] = det.detectar(db, user.id, perfil.id,
                                          m.get("descripcion") or "", m["tipo"],
                                          m["monto"], fecha.day)
        # El bot tiene que poder LEER el nombre de la categoria, asi que aqui no
        # se borra como en la respuesta de la web.
    p["captura_id"] = reg.id
    return p


def confirmar_captura(db: Session, user, perfil, captura_id: str,
                      movimientos: list[dict], idempotency_key: str | None = None) -> dict:
    """Escribe los movimientos que el usuario acepto. Devuelve resumen y errores.

    Es idempotente por `captura_id`: si la captura ya quedo en "guardado" no se
    vuelve a escribir. WhatsApp reintenta entregas y el usuario puede mandar
    "sí" dos veces; sin esto se le duplicarian los gastos.
    """
    from app.models.captura import Captura
    from app.models.goals import Recurring

    reg = db.query(Captura).filter_by(id=captura_id, user_id=user.id,
                                      perfil_id=perfil.id).first()
    if not reg:
        raise ValueError("Captura no encontrada")
    if reg.estado == "guardado":
        return {"guardados": [], "errores": [], "creados": 0, "ya_guardada": True}

    creados, errores = [], []
    for i, m in enumerate(movimientos):
        try:
            cuenta = resolver_cuenta(db, perfil.id, m.get("cuenta_id"))
            if not cuenta:
                raise ValueError("No tienes ninguna cuenta en este perfil")
            cat = db.query(Category).filter_by(id=m.get("categoria_id"), perfil_id=perfil.id).first()
            if not cat:
                raise ValueError("La categoría no existe en este perfil")
            if cat.tipo not in (m.get("tipo"), "ambos"):
                raise ValueError(f"La categoría {cat.nombre} no admite {m.get('tipo')}s")
            met = None
            if m.get("metodo_id"):
                met = db.query(PaymentMethod).filter_by(id=m["metodo_id"], user_id=user.id).first()
            fecha = validar_fecha(m.get("fecha"))
            mov = Transaction(
                user_id=user.id, perfil_id=perfil.id, cuenta_id=cuenta.id,
                categoria_id=cat.id, metodo_id=met.id if met else None,
                tipo=m.get("tipo"), monto=m["monto"], fecha=fecha,
                descripcion=m.get("descripcion") or cat.nombre,
                idempotency_key=idempotency_key,
            )
            db.add(mov)
            db.flush()
            creados.append({"id": mov.id, "tipo": mov.tipo, "monto": float(mov.monto),
                            "categoria": cat.nombre, "fecha": mov.fecha.isoformat()})

            # Enlace a un fijo ya declarado por el usuario ("sí, es el mismo").
            rec = None
            if m.get("recurrente_id"):
                rec = db.query(Recurring).filter_by(id=m["recurrente_id"],
                                                    perfil_id=perfil.id).first()
            if rec:
                mov.recurrente_id = rec.id
                rec.confirmado = True
            elif m.get("recurrente_id"):
                errores.append({"indice": i,
                                "detalle": "Ese fijo no es de este perfil; se guardó sin enlace"})

            if m.get("nuevo_fijo"):
                nombre_fijo = (m.get("descripcion") or cat.nombre)[:120]
                ya = db.query(Recurring).filter_by(perfil_id=perfil.id, nombre=nombre_fijo,
                                                    dia=fecha.day, tipo=m.get("tipo"),
                                                    activo=True).first()
                if not ya:
                    db.add(Recurring(user_id=user.id, perfil_id=perfil.id,
                                     nombre=nombre_fijo, tipo=m.get("tipo"), monto=m["monto"],
                                     dia=fecha.day, frecuencia="mensual",
                                     cuenta_id=cuenta.id, categoria_id=cat.id, activo=True,
                                     confirmado=True, nota="Creado desde la captura"))
            elif m.get("fijo") and not rec and not db.query(
                    Recurring).filter_by(perfil_id=perfil.id, cuenta_id=cuenta.id,
                                        categoria_id=cat.id, tipo=m.get("tipo"),
                                        activo=True).first():
                db.add(Recurring(user_id=user.id, perfil_id=perfil.id,
                                 nombre=m.get("descripcion") or cat.nombre,
                                 tipo=m.get("tipo"), monto=m["monto"], dia=fecha.day,
                                 frecuencia="mensual", cuenta_id=cuenta.id,
                                 categoria_id=cat.id, activo=True))
        except Exception as e:  # noqa: BLE001 - se reporta por movimiento, no se cae todo
            errores.append({"indice": i, "detalle": str(e)})

    reg.estado = "guardado" if not errores else "parcial"
    reg.guardados = len(creados)
    db.commit()
    return {"guardados": creados, "errores": errores, "creados": len(creados)}
