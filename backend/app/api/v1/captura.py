"""Captura en lenguaje natural: escribir (o hablar) una frase y registrar.

Flujo, en dos pasos a proposito:
  1. POST /captura            -> devuelve una PROPUESTA, no escribe nada.
  2. POST /captura/confirmar  -> guarda lo que el usuario acepta.

Por que dos pasos: el modelo se equivoca. Si guarda directo, un monto mal leido
queda en la base como si fuera real y el usuario no se entera hasta ver un
resumen raro semanas despues.

Reglas de producto que quedaron definidas:
- Confirmacion con un toque siempre.
- Si el modelo NO leyo el monto del texto, la UI exige confirmarlo a mano
  (requiere_confirmacion_monto). Si lo leyo, basta un toque.
- Atajo opcional "guardar siempre" para quien ya confia en la app.
"""
import json
from typing import Literal

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.core.plan import consumo_captura, consumir_captura
from app.core.ratelimit import captura_limit
from app.models.captura import Captura
from app.models.finance import Account, Category, PaymentMethod, Transaction
from app.models.goals import Recurring
from app.models.perfil import Perfil
from app.models.user import User
from app.services import captura as cap
from app.services import captura_confirmar as capx
from app.services import colombia as co
from app.services import deteccion as det

router = APIRouter(tags=["captura"])


class CapturaIn(BaseModel):
    texto: str = Field(min_length=1, max_length=500)
    # Cuando el texto vino de una nota de voz, para la auditoria y el /datos.
    transcripcion: bool = False


class MovimientoAConfirmar(BaseModel):
    tipo: Literal["gasto", "ingreso"]
    monto: float = Field(gt=0)
    categoria_id: str
    descripcion: str = Field(default="", max_length=200)
    metodo_id: str | None = None
    cuenta_id: str | None = None
    fecha: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    fijo: bool = False
    # Que fijo YA DECLARADO es este movimiento. Lo llena el usuario cuando la app
    # pregunta "Â¿es el mismo Arriendo o uno distinto?". Si viene None y el
    # movimiento se parece a un fijo existente, se guarda sin enlazar: el
    # movimiento es real de todos modos, lo unico que se pierde es la linea que
    # lo ataba al plan. Perder el enlace es mucho mejor que bloquear el gasto.
    recurrente_id: str | None = None
    # Crear ademas un fijo NUEVO con este movimiento. Para cuando el usuario
    # responde "es distinto": no es el Arriendo de siempre sino, digamos, un
    # arriendo en otro apartamento o el celular que renueva cada mes.
    nuevo_fijo: bool = False
    # Periodicidad que la captura leyo del texto ("cada quincena"). La leyo la
    # propuesta y se respeta al crear el fijo; None = mensual, como siempre.
    frecuencia: Literal["mensual", "quincenal", "semanal"] | None = None
    dia_fijo: int | None = Field(default=None, ge=1, le=31)
    # Dia de la semana del fijo semanal: 0=lunes .. 6=domingo. Sin esto, "me
    # pagan cada domingo" se guardaba anclado a un dia del mes que el mes
    # siguiente ya no era domingo.
    dia_semana: int | None = Field(default=None, ge=0, le=6)


class CapturaConfirmarIn(BaseModel):
    captura_id: str
    movimientos: list[MovimientoAConfirmar] = Field(min_length=1, max_length=20)
    # El usuario acepto ver la propuesta y tocar guardar: no se vuelve a preguntar
    # aunque algun monto viniera dudoso.
    confirmacion_usuario: bool = False


@router.get("/captura/uso")
def uso(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Consumo de hoy, para pintar 'te quedan N' en la pastilla de captura."""
    estado = consumo_captura(db, user)
    estado["confirmar_siempre"] = settings.captura_confirmar_siempre
    return estado


@router.post("/captura", dependencies=[Depends(captura_limit)])
def capturar(data: CapturaIn, db: Session = Depends(get_db),
             user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil)):
    """Analiza la frase y devuelve una propuesta. NO escribe movimientos."""
    cuota = consumir_captura(db, user)
    try:
        propuesta = capx.proponer(db, user, perfil, data.texto, data.transcripcion)
    except cap.CapturaError as e:
        _bitacora(db, user, perfil, data, "error", [], 0, False)
        db.commit()
        raise HTTPException(422, str(e))

    # Ojo: la cuota se consume UNA sola vez, aqui arriba. Consumirla tambien al
    # confirmar castigaria al usuario cada vez que el "Guardar" se rebotaba.
    return {**propuesta, "cuota": cuota, "opciones": _opciones(db, user, perfil)}


@router.post("/captura/confirmar")
def confirmar(data: CapturaConfirmarIn, db: Session = Depends(get_db),
              user: User = Depends(get_current_user), perfil: Perfil = Depends(get_perfil),
              idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    """Guarda lo que el usuario acepto. Ahi es donde se escriben movimientos."""
    reg = db.query(Captura).filter_by(id=data.captura_id, user_id=user.id,
                                        perfil_id=perfil.id).first()
    if not reg:
        raise HTTPException(404, "Captura no encontrada")
    if reg.estado == "guardado":
        raise HTTPException(409, "Esta captura ya se guardÃ³")

    dudosos = [m for m in data.movimientos
               if any(p["ix"] == i and p["requiere_confirmacion_monto"]
                      for i, p in enumerate(json.loads(reg.propuestos or "[]")))]
    # El monto que el modelo dedujo (no leido del texto) exige confirmacion
    # explicita. "confirmar siempre" la exige SIEMPRE.
    if settings.captura_confirmar_siempre and not data.confirmacion_usuario:
        raise HTTPException(
            422,
            "Falta la confirmaciÃ³n del usuario. Se pide explÃ­citamente para no "
            "guardar cifras que la IA dedujo en vez de leerlas.",
        )

# A partir de aqui la escritura vive en el servicio: el bot de WhatsApp
    # entra por la misma puerta y no puede quedar una copia que se desvÃ­e.
    try:
        return capx.confirmar_captura(db, user, perfil, data.captura_id,
                                      [m.model_dump() for m in data.movimientos],
                                      idempotency_key)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/captura/voz", dependencies=[Depends(captura_limit)])
def capturar_voz(
    audio: UploadFile = File(..., description="Audio de la nota de voz (webm/ogg/mp4/m4a/wav)."),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    perfil: Perfil = Depends(get_perfil),
):
    """Transcribe una nota de voz y devuelve la MISMA propuesta que /captura.

    El audio se transcribe y se descarta: no se guarda en la base ni en disco.
    Solo queda el texto en la bitacora de capturas, y el usuario puede borrarla.
    """
    cuota = consumir_captura(db, user)
    nombre = audio.filename or "nota.webm"
    try:
        datos = audio.file.read()
        texto = cap.transcribir(datos, nombre, audio.content_type or "")
    except cap.CapturaError as e:
        raise HTTPException(422, str(e))
    finally:
        audio.file.close()

    if not cap._tiene_indicios(texto, db):
        raise HTTPException(
            422,
            f"EscuchÃ© \"{texto}\" pero no encontrÃ© ningÃºn gasto ahÃ­. "
            "Prueba algo como: \"gastÃ© 18 mil en el almuerzo\".",
        )
    try:
        propuesta = cap.analizar(texto, db, user.id, perfil.id)
    except cap.CapturaError as e:
        raise HTTPException(422, str(e))

    reg = _bitacora(db, user, perfil, CapturaIn(texto=texto, transcripcion=True),
                    "propuesta", propuesta["movimientos"], 0,
                    propuesta["requiere_confirmacion_monto"])
    db.commit()

    return {**_opciones(db, user, perfil), **propuesta,
            "captura_id": reg.id, "cuota": cuota,
            "opciones": _opciones(db, user, perfil)}


def _opciones(db: Session, user: User, perfil: Perfil) -> dict:
    """Listas para que la UI pueda corregir categorÃ­a, cuenta y mÃ©todo."""
    cats = db.query(Category).filter_by(perfil_id=perfil.id, activa=True).all()
    cuentas = db.query(Account).filter_by(perfil_id=perfil.id).order_by(Account.nombre).all()
    mets = db.query(PaymentMethod).filter_by(user_id=user.id).order_by(PaymentMethod.nombre).all()
    return {
        "categorias": [{"id": c.id, "nombre": c.nombre, "tipo": c.tipo} for c in cats],
        "cuentas": [{"id": c.id, "nombre": c.nombre, "tipo": c.tipo,
                     "saldo_actual": float(c.saldo_inicial)} for c in cuentas],
        "metodos": [{"id": m.id, "nombre": m.nombre} for m in mets],
    }


def _validar_fecha(iso: str):
    from datetime import date, timedelta

    try:
        f = date.fromisoformat(iso)
    except ValueError:
        raise ValueError("Fecha invÃ¡lida")
    if f > date.today() + timedelta(days=1):
        raise ValueError("La fecha no puede ser mÃ¡s de 1 dÃ­a en el futuro")
    return f


def _resolver_cuenta(db: Session, perfil_id: str, cuenta_id: str | None) -> Account | None:
    if cuenta_id:
        c = db.query(Account).filter_by(id=cuenta_id, perfil_id=perfil_id).first()
        if c:
            return c
        raise ValueError("Esa cuenta no existe en este perfil")
    return db.query(Account).filter_by(perfil_id=perfil_id).order_by(Account.nombre).first()


def _bitacora(db: Session, user: User, perfil: Perfil, data: CapturaIn, estado: str,
              propuestos: list, guardados: int, monto_dudoso: bool) -> Captura:
    reg = Captura(user_id=user.id, perfil_id=perfil.id, texto=data.texto,
                  transcripcion=data.transcripcion, estado=estado,
                  propuestos=json.dumps(propuestos, ensure_ascii=False, default=str),
                  guardados=guardados, monto_dudoso=monto_dudoso)
    db.add(reg)
    db.flush()
    return reg
