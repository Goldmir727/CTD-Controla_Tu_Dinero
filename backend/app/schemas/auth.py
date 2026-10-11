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
    # Lo deduce el navegador (navigator.language) y el usuario puede cambiarlo
    # en Ajustes. Nullable de entrada para no romper registros ya hechos.
    pais: str | None = Field(default=None, min_length=2, max_length=2)
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
    # Cambiar el pais cambia el formato entero y, si el pais usa quincena, la
    # forma de razonar de la app. La moneda se ajusta sola para que no queden
    # las dos cosas en contra: elegir Mexico y que siga diciendo COP no sirve.
    pais: str | None = Field(default=None, min_length=2, max_length=2)
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
    # El pais define COMO se escribe el numero (separadores, idioma, quincena).
    # La MONEDA es la unidad y no se toca sola: ver el aviso de abajo.
    pais: str = "CO"
    pais_nombre: str = "Colombia"
    usa_quincena: bool = True
    locale: str = "es-CO"
    # Aparece cuando el pais del usuario no usa su moneda. La app no convierte:
    # 1.800.000 pesos siguen siendo 1.800.000 pesos aunque el pais sea otro.
    aviso_moneda: str | None = None
    # Que puede usar este usuario, para que el front no adivine reglas.
    capacidades: dict[str, bool] = Field(default_factory=dict)
    asesor_consultas_dia: int = 5


def user_out(user, aviso: str | None = None) -> UserOut:
    from app.core.plan import config_plan, plan_efectivo
    from app.core.legal import DATOS_VERSION, TERMINOS_VERSION
    from app.services import paises
    from app.services.formato import simbolo_moneda

    cfg = config_plan(user)
    # La version importa igual que la fecha: si los documentos cambiaron, hay que
    # volver a pedir el consentimiento aunque el usuario ya lo hubiera dado.
    return UserOut(id=user.id, nombre=user.nombre, correo=user.correo, moneda=user.moneda,
                   foto_url=user.foto_url,
                   onboarding_done=user.onboarding_done, is_2fa_enabled=user.is_2fa_enabled,
                   acepta_terminos=(user.acepta_terminos_at is not None
                                    and user.terminos_version == TERMINOS_VERSION),
                   acepta_datos=(user.acepta_datos_at is not None
                                 and user.datos_version == DATOS_VERSION),
                   plan=plan_efectivo(user),
                   simbolo_moneda=simbolo_moneda(user.moneda),
    pais=(user.pais or paises.DEFAULT),
    pais_nombre=paises.nombre(user.pais),
    aviso_moneda=aviso,
    usa_quincena=paises.usa_quincena(user.pais),
    locale=paises.locale_de(user.pais, user.moneda),
                   capacidades={k: bool(v) for k, v in cfg.items() if isinstance(v, bool)},
                   asesor_consultas_dia=int(cfg["asesor_dia"]))


class ConsentimientoIn(BaseModel):
    acepta_terminos: bool = False
    acepta_datos: bool = False
