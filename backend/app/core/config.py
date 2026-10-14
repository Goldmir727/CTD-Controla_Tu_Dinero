from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Valores que aparecen en .env.example o como default. Firmar con cualquiera de
# ellos es tan inseguro como no tener autenticacion.
_SECRETS_POR_DEFECTO = {
    "dev_secret_cambiar_en_prod",
    "cambia_este_secreto_en_produccion_min32chars",
    "cambia_este_secreto_en_produccion",
    "changeme",
    "secret",
}


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://finanzas:finanzas_dev@localhost:5432/finanzas"
    jwt_secret: str = "dev_secret_cambiar_en_prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_min: int = 30
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://localhost:3000"]
    # Email 2FA (Gmail SMTP). Si no hay SMTP, el código se loguea (dev).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "CTD <no-reply@ctd.app>"
    twofa_ttl_min: int = 10
    twofa_max_attempts: int = 5
    twofa_cooldown_s: int = 60
    redis_url: str = "redis://localhost:6379/0"
    # Asesor IA (plan separado, OpenAI). Sin clave → 503 explicativo.
    openai_api_key: str = ""
    asesor_model: str = "gpt-4o-mini"
    # Compatible OpenAI: Groq (gratis) u Ollama local. Ejemplos:
    # Groq:  ASESOR_BASE_URL=https://api.groq.com/openai/v1  ASESOR_MODEL=openai/gpt-oss-20b
    # Ollama: ASESOR_BASE_URL=http://host.docker.internal:11434/v1  ASESOR_MODEL=llama3.1
    asesor_base_url: str = "https://api.openai.com/v1"
    # OJO: los modelos de razonamiento (gpt-oss, o1/o3) gastan tokens pensando ANTES
    # de responder. Con un tope bajo se quedan sin presupuesto y devuelven texto vacío,
    # así que el mínimo realista es ~2000.
    asesor_max_tokens: int = 2000
    # low|medium|high para modelos que lo soportan (gpt-oss en Groq). Vacío = no enviar
    # (OpenAI gpt-4o-mini rechaza el parámetro).
    asesor_reasoning_effort: str = "low"
    asesor_max_dia: int = 20
    # Captura en lenguaje natural. Es un camino distinto al chat: el usuario escribe
    # o habla una frase y la app propone movimientos.
    captura_max_dia: int = 40
    # Cuando esta en false, el usuario SIEMPRE tiene que tocar "Guardar" antes de
    # que se escriba algo. Con true, lo que este seguro se guarda de una.
    captura_confirmar_siempre: bool = True
    # Nota de voz. Whisper de Groq con la misma clave que el asesor.
    # El audio NO se guarda en ningun lado: se transcribe y se descarta.
    voz_model: str = "whisper-large-v3-turbo"
    voz_max_segundos: int = 30
    voz_max_bytes: int = 8_000_000

    # ---- Cobros (Wompi / Bancolombia) ----
    # Todo vacio = el cobro queda deshabilitado y la app sigue funcionando en
    # modo manual. Asi se puede desplegar sin credenciales y activarlas depois.
    wompi_public_key: str = ""
    # Secreto de "Secretos para integracion tecnica" del dashboard de Wompi.
    # Es lo unico que separa un webhook real de uno forjado: sin esto, cualquiera
    # que sepa la URL podria activarse PRO a si mismo.
    wompi_events_secret: str = ""
    # Enlace de pago recurrente del plan PRO, creado en el dashboard de Wompi.
    # Wompi cobra solo cada mes; la app solo extiende el vencimiento cada vez que
    # llega un evento APPROVED.
    wompi_enlace_pro: str = ""
    # Precio en COP. Solo para mostrarlo; el cobro real lo hace Wompi.
    pro_precio_mes: int = 15_000
    pro_dias_periodo: int = 30

    # ---- Bot de WhatsApp (Cloud API de Meta) ----
    # Todo vacio = el bot queda apagado y la API responde 503 sin molestar.
    # Es el estado por defecto: el codigo se despliega antes de que exista la
    # cuenta de Meta.
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    # Token que uno mismo inventa y configura en el panel de Meta para que
    # verifique que el webhook es el suyo.
    whatsapp_verify_token: str = ""
    # App Secret de Meta: con esto se valida la firma X-Hub-Signature-256.
    # Sin el, cualquiera que mande un POST a /whatsapp/webhook podria usar el
    # bot y gastar llamadas de la IA.
    whatsapp_app_secret: str = ""
    # Cuota diaria por telefono SINvinculo, para que el bot no se convierta en
    # una puerta abierta a gastar la clave de Groq.
    whatsapp_sin_vinculo_dia: int = 3

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        # Sin NoDecode, pydantic-settings hace json.loads antes y revienta con "a,b".
        # Acepta JSON '["a","b"]' o coma 'a,b' (docker-compose usa coma).
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                import json

                try:
                    return json.loads(s)
                except Exception:
                    pass
            return [p.strip() for p in s.split(",") if p.strip()]
        return v

    @model_validator(mode="after")
    def _jwt_secret_usable(self):
        """Convierte "acordate de cambiar el secreto" en un error imposible de ignorar.

        Con un JWT_SECRET débil o conocido, cualquiera puede firmar tokens con
        cualquier user_id y entrar como ese usuario. Antes esto fallaba en silencio.
        """
        s = (self.jwt_secret or "").strip()
        if not s:
            # Dev: genera uno efimero. Reiniciar invalida los tokens, sin ruido.
            import logging
            import secrets

            logging.getLogger(__name__).warning(
                "JWT_SECRET no configurado: se genera uno aleatorio para esta ejecucion. "
                "Los tokens no sobreviviran un reinicio. Define JWT_SECRET en .env para produccion."
            )
            object.__setattr__(self, "jwt_secret", secrets.token_urlsafe(48))
            return self
        if s.lower() in _SECRETS_POR_DEFECTO:
            raise ValueError(
                "JWT_SECRET sigue siendo el valor de ejemplo de .env.example. "
                "Cualquiera que lo conozca puede firmar tokens de administrador. "
                "Genera uno real con: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if len(s) < 32:
            raise ValueError(
                f"JWT_SECRET tiene {len(s)} caracteres; minimo 32. "
                "Genera uno con: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return self

    # pydantic-settings v2: `class Config` esta deprecado, se usa model_config.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
