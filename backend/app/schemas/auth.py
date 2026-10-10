from typing import Annotated

from pydantic import BaseModel, BeforeValidator, EmailStr, Field


def _norm_correo(v):
    # Teclados móviles agregan espacios/mayúsculas: normalizar antes de validar.
    return v.strip().lower() if isinstance(v, str) else v


CorreoLimpio = Annotated[EmailStr, BeforeValidator(_norm_correo)]


class RegistroIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    correo: CorreoLimpio
    password: str = Field(min_length=8)
    moneda: str = Field(default="COP", pattern="^(COP|USD|MXN|EUR)$")
    foto_url: str | None = None
    acepta_terminos: bool = False
    acepta_datos: bool = False


class LoginIn(BaseModel):
    correo: CorreoLimpio
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_in: int = 1800


class RefreshIn(BaseModel):
    refresh_token: str


class UserPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    moneda: str | None = Field(default=None, pattern="^(COP|USD|MXN|EUR)$")
    foto_url: str | None = None


class LoginOut(BaseModel):
    requires_2fa: bool = False
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_in: int = 1800


class TwoFaSolicitarIn(BaseModel):
    correo: CorreoLimpio


class TwoFaVerificarIn(BaseModel):
    correo: CorreoLimpio
    code: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")


class TwoFaActivarIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")


class OnboardingCuentaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = Field(default="efectivo", pattern="^(efectivo|banco|bolsa|otro)$")
    monto: float = Field(ge=0)

class OnboardingIn(BaseModel):
    modo: str = Field(pattern="^(todo_junto|separadas)$")
    total: float = Field(default=0, ge=0)  # solo se usa en todo_junto; en separadas se calcula
    cuentas: list[OnboardingCuentaIn] = []


class CorreoCambiarIn(BaseModel):
    nuevo_correo: CorreoLimpio
    password: str = Field(min_length=1)


class PasswordSolicitarIn(BaseModel):
    correo: CorreoLimpio


class PasswordConfirmarIn(BaseModel):
    correo: CorreoLimpio
    code: str = Field(min_length=10, max_length=10, pattern="^[0-9]{10}$")
    nueva_password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: str
    nombre: str
    correo: str
    moneda: str
    foto_url: str | None = None
    onboarding_done: bool = False
    is_2fa_enabled: bool = False
    acepta_terminos: bool = False
    acepta_datos: bool = False
    # Plan comercial: "free" | "pro" (ya vencido se reporta como "free").
    plan: str = "free"
    simbolo_moneda: str = "$"
    # Que puede usar este usuario, para que el front no adivine reglas.
    capacidades: dict[str, bool] = Field(default_factory=dict)
    asesor_consultas_dia: int = 5


def user_out(user) -> UserOut:
    from app.core.plan import config_plan, plan_efectivo
    from app.services.formato import simbolo_moneda

    cfg = config_plan(user)
    return UserOut(id=user.id, nombre=user.nombre, correo=user.correo, moneda=user.moneda,
                   foto_url=user.foto_url,
                   onboarding_done=user.onboarding_done, is_2fa_enabled=user.is_2fa_enabled,
                   acepta_terminos=user.acepta_terminos_at is not None,
                   acepta_datos=user.acepta_datos_at is not None,
                   plan=plan_efectivo(user),
                   simbolo_moneda=simbolo_moneda(user.moneda),
                   capacidades={k: bool(v) for k, v in cfg.items() if isinstance(v, bool)},
                   asesor_consultas_dia=int(cfg["asesor_dia"]))


class ConsentimientoIn(BaseModel):
    acepta_terminos: bool = False
    acepta_datos: bool = False
