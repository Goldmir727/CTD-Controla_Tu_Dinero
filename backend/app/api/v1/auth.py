import smtplib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.legal import DATOS_VERSION, TERMINOS_VERSION
from app.core.deps import get_current_user, get_perfil
from app.core.ratelimit import login_limit, pw_confirmar_limit, pw_solicitar_limit, solicitar_limit, verificar_limit
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.finance import Account, Budget, Category, PaymentMethod, Transaction
from app.models.perfil import Perfil
from app.models.user import User
from app.schemas.auth import ConsentimientoIn, CorreoCambiarIn, LoginIn, LoginOut, OnboardingIn, PasswordConfirmarIn, PasswordSolicitarIn, RefreshIn, RegistroIn, TokenOut, TwoFaActivarIn, TwoFaSolicitarIn, TwoFaVerificarIn, UserOut, UserPatch, user_out
from app.services import password_reset as pw_svc
from app.services import twofa as twofa_svc

router = APIRouter(tags=["auth"])

SEED_CATS = [
    ("Comida", "gasto"), ("Transporte", "gasto"), ("Vivienda", "gasto"),
    ("Salud", "gasto"), ("Ocio", "gasto"), ("Educación", "gasto"),
    ("Salario", "ingreso"), ("Freelance", "ingreso"), ("Otros", "ambos"),
    ("Servicios", "gasto"), ("Mercado", "gasto"), ("Familia", "gasto"),
    ("Impuestos", "gasto"),
]
# Efectivo/Tarjeta/Transferencia + las carteras que mas se usan en Colombia.
SEED_METODOS = ["Efectivo", "Tarjeta", "Transferencia",
                "Nequi", "Daviplata", "Dale", "PSE", "Nómina"]





@router.post("/auth/registro", response_model=UserOut, status_code=201)
def registro(data: RegistroIn, db: Session = Depends(get_db)):
    from datetime import datetime, timezone

    if not data.acepta_terminos or not data.acepta_datos:
        raise HTTPException(status_code=422, detail="Debes aceptar los Términos y la Política de Datos para crear tu cuenta.")
    if db.query(User).filter_by(correo=data.correo).first():
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado")
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    from app.services.imagenes import validar_imagen
    validar_imagen(data.foto_url, 300_000)
    user = User(nombre=data.nombre, correo=data.correo, password_hash=hash_password(data.password), moneda=data.moneda,
                foto_url=data.foto_url,
                acepta_terminos_at=ahora, terminos_version=TERMINOS_VERSION,
                acepta_datos_at=ahora, datos_version=DATOS_VERSION)
    db.add(user)
    db.flush()
    # Todo usuario nace con un perfil "Personal" que es su principal. Las filas
    # cuelgan de el: es lo que permite separar despues las finanzas del negocio.
    perfil = Perfil(user_id=user.id, nombre="Personal", tipo="personal", principal=True)
    db.add(perfil)
    db.flush()
    _sembrar_perfil(db, user.id, perfil.id)
    db.commit()
    db.refresh(user)
    return user_out(user)


def _sembrar_perfil(db: Session, user_id: str, perfil_id: str) -> None:
    """Crea las filas base de un perfil: una cuenta, las categorias y los metodos."""
    db.add(Account(user_id=user_id, perfil_id=perfil_id, nombre="Efectivo",
                   tipo="efectivo", saldo_inicial=0))
    for nombre, tipo in SEED_CATS:
        db.add(Category(user_id=user_id, perfil_id=perfil_id, nombre=nombre, tipo=tipo))
    for nombre in SEED_METODOS:
        db.add(PaymentMethod(user_id=user_id, nombre=nombre))


@router.post("/auth/login", response_model=LoginOut, dependencies=[Depends(login_limit)])
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(correo=data.correo).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    if user.is_2fa_enabled:
        try:
            twofa_svc.emitir(db, user.id, user.correo)
        except twofa_svc.CooldownError as e:
            raise HTTPException(status_code=429, detail=f"Ya enviamos un código. Espera {e.retry_after}s y revisa tu correo.")
        except smtplib.SMTPException:
            raise HTTPException(status_code=502, detail="No se pudo enviar el código al correo. Revisa la configuración SMTP o intenta más tarde.")
        return LoginOut(requires_2fa=True)
    return LoginOut(requires_2fa=False, access_token=create_access_token(user.id), refresh_token=create_refresh_token(user.id))


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    user_id = decode_token(data.refresh_token, want="refresh")
    if not user_id or not db.get(User, user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido o vencido")
    # Rotación: cada uso emite un refresh nuevo; el anterior queda obsoleto en cliente.
    return TokenOut(access_token=create_access_token(user_id), refresh_token=create_refresh_token(user_id))


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/auth/me", response_model=UserOut)
def patch_me(data: UserPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.imagenes import validar_imagen

    patch = data.model_dump(exclude_unset=True)
    if "foto_url" in patch:
        validar_imagen(patch["foto_url"], 300_000)
        user.foto_url = patch.pop("foto_url") or None
    for k, v in patch.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/auth/logout")
def logout():
    # JWT stateless: el frontend borra tokens. Blacklist server en Fase 4.
    return {"ok": True}


@router.post("/auth/2fa/solicitar", dependencies=[Depends(solicitar_limit)])
def solicitar_2fa(data: TwoFaSolicitarIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(correo=data.correo).first()
    # Respuesta genérica para no enumerar correos
    if user:
        try:
            twofa_svc.emitir(db, user.id, user.correo)
        except twofa_svc.CooldownError as e:
            raise HTTPException(status_code=429, detail=f"Ya enviamos un código. Espera {e.retry_after}s y revisa tu correo.")
        except smtplib.SMTPException:
            raise HTTPException(status_code=502, detail="No se pudo enviar el correo. Revisa la configuración SMTP o intenta más tarde.")
    return {"ok": True, "mensaje": "Si el correo existe, enviamos un código de 6 dígitos."}


@router.post("/auth/2fa/verificar", response_model=TokenOut, dependencies=[Depends(verificar_limit)])
def verificar_2fa(data: TwoFaVerificarIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(correo=data.correo).first()
    if not user or not twofa_svc.verificar(db, user.id, data.code):
        raise HTTPException(status_code=401, detail="Código inválido o vencido")
    return TokenOut(access_token=create_access_token(user.id), refresh_token=create_refresh_token(user.id))


@router.post("/auth/2fa/activar")
def activar_2fa(data: TwoFaActivarIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Usuario ya autenticado: no se pide correo (era la causa del 422 desde Ajustes).
    if not twofa_svc.verificar(db, user.id, data.code):
        raise HTTPException(status_code=401, detail="Código inválido o vencido")
    user.is_2fa_enabled = True
    db.commit()
    return {"ok": True, "is_2fa_enabled": True}


@router.post("/auth/2fa/desactivar")
def desactivar_2fa(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.is_2fa_enabled = False
    db.commit()
    return {"ok": True, "is_2fa_enabled": False}


@router.get("/auth/2fa/estado")
def estado_2fa(user: User = Depends(get_current_user)):
    return {"is_2fa_enabled": user.is_2fa_enabled}


@router.post("/auth/cuenta/reiniciar")
def reiniciar_cuenta(confirm: bool = False, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """Borra TODO lo financiero (movimientos, presupuestos, metas, cuentas, códigos)
    y deja la cuenta lista para un onboarding nuevo. La sesión y el login se conservan.

    Se borran tambien los perfiles no principales: el usuario pidió empezar de cero.
    """
    from app.models.goals import Goal, GoalAporte, Recurring
    from app.models.password import PasswordCode
    from app.models.twofa import TwoFaCode

    if not confirm:
        raise HTTPException(status_code=422, detail="Confirma con ?confirm=true")
    principal = db.query(Perfil).filter_by(user_id=user.id, principal=True).first()
    if not principal:
        raise HTTPException(status_code=500, detail="El usuario no tiene perfil principal")
    # Primero los perfiles secundarios: sus filas tienen FK hacia ellos.
    for p in db.query(Perfil).filter_by(user_id=user.id).all():
        if p.id != principal.id:
            for model in (Transaction, Budget, GoalAporte, Goal, Recurring):
                db.query(model).filter_by(user_id=user.id, perfil_id=p.id).delete()
            db.delete(p)
    for model in (Transaction, Budget, GoalAporte, Goal, Recurring,
                  PasswordCode, TwoFaCode, PaymentMethod, Category, Account):
        db.query(model).filter_by(user_id=user.id).delete()
    _sembrar_perfil(db, user.id, principal.id)
    user.onboarding_done = False
    db.commit()
    return {"ok": True}


@router.post("/auth/consentimiento", response_model=UserOut)
def consentimiento(data: ConsentimientoIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Registra la aceptación de los documentos.

    Se rellena si falta la fecha O si la versión no es la vigente. Solo mirar la
    fecha hacia que, tras subir de versión, el ConsentBanner apareciera siempre
    y el usuario no pudiera cerrarlo nunca.
    """
    from datetime import datetime, timezone

    if not data.acepta_terminos or not data.acepta_datos:
        raise HTTPException(status_code=422, detail="Debes aceptar ambos documentos.")
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.acepta_terminos_at is None or user.terminos_version != TERMINOS_VERSION:
        user.acepta_terminos_at = ahora
        user.terminos_version = TERMINOS_VERSION
    if user.acepta_datos_at is None or user.datos_version != DATOS_VERSION:
        user.acepta_datos_at = ahora
        user.datos_version = DATOS_VERSION
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/auth/correo/cambiar", response_model=UserOut)
def cambiar_correo(data: CorreoCambiarIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Cambiar correo exige confirmar la contraseña actual.
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    if db.query(User).filter_by(correo=data.nuevo_correo).first():
        raise HTTPException(status_code=409, detail="Ese correo ya está en uso")
    user.correo = data.nuevo_correo
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/auth/password/solicitar", dependencies=[Depends(pw_solicitar_limit)])
def solicitar_password(data: PasswordSolicitarIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(correo=data.correo).first()
    # Respuesta genérica para no enumerar correos
    if user:
        try:
            pw_svc.emitir(db, user.id, user.correo)
        except pw_svc.CooldownError as e:
            raise HTTPException(status_code=429, detail=f"Ya enviamos un código. Espera {e.retry_after}s y revisa tu correo.")
        except smtplib.SMTPException:
            raise HTTPException(status_code=502, detail="No se pudo enviar el correo. Revisa la configuración SMTP o intenta más tarde.")
    return {"ok": True, "mensaje": "Si el correo existe, enviamos un código de 10 dígitos."}


@router.post("/auth/password/confirmar", dependencies=[Depends(pw_confirmar_limit)])
def confirmar_password(data: PasswordConfirmarIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(correo=data.correo).first()
    if not user or not pw_svc.verificar(db, user.id, data.code):
        raise HTTPException(status_code=401, detail="Código inválido o vencido")
    user.password_hash = hash_password(data.nueva_password)
    db.commit()
    return {"ok": True}


@router.post("/onboarding/completar")
def onboarding(data: OnboardingIn, db: Session = Depends(get_db),
               user: User = Depends(get_current_user),
               perfil: Perfil = Depends(get_perfil)):
    """Todo junto: 1 cuenta con el total. Separadas: la app SUMA las partes, el
    usuario nunca cuadra nada (el total se ignora y se calcula)."""
    if user.onboarding_done:
        raise HTTPException(409, "Onboarding ya completado")
    if data.modo == "todo_junto":
        acc = db.query(Account).filter_by(user_id=user.id, perfil_id=perfil.id).first()
        if not acc:
            acc = Account(user_id=user.id, perfil_id=perfil.id, nombre="Efectivo",
                          tipo="efectivo", saldo_inicial=data.total)
            db.add(acc)
        else:
            if db.query(Transaction).filter_by(cuenta_id=acc.id).count() > 0:
                raise HTTPException(409, "Ya tienes movimientos, ajusta con un ingreso")
            acc.saldo_inicial = data.total
        total = float(data.total)
    else:
        if not data.cuentas or not any(c.nombre.strip() for c in data.cuentas):
            raise HTTPException(422, "Agrega al menos 1 cuenta con nombre")
        # Limpia seed de 0 para no duplicar
        for a in db.query(Account).filter_by(user_id=user.id, perfil_id=perfil.id).all():
            if db.query(Transaction).filter_by(cuenta_id=a.id).count() == 0 and float(a.saldo_inicial) == 0:
                db.delete(a)
        total = 0.0
        for c in data.cuentas:
            if not c.nombre.strip():
                continue
            monto = max(float(c.monto or 0), 0)
            total += monto
            db.add(Account(user_id=user.id, perfil_id=perfil.id, nombre=c.nombre.strip(),
                           tipo=c.tipo, saldo_inicial=monto))
    user.onboarding_done = True
    db.commit()
    return {"ok": True, "total": round(total, 2)}

