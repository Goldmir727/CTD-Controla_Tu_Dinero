"""Autenticacion: el token de refresh no debe servir como credencial de acceso.

Regresion grave: get_current_user llamaba decode_token(tok) sin want="access", asi
que un refresh token (7 dias de vida) daba acceso completo saltandose el TTL de
30 minutos del access token.
"""
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token

UID = "e9a1f0e2-0000-4000-8000-000000000001"
# Secreto de ejemplo que se usaba en .env antes de rotarlo.
VIEJO = "ybygbygbybubuhashdsahbusandnasdnsamdasmuhnsadiasidnasnu__w"


def _firmar(claims, secreto):
    return jwt.encode({"sub": UID, "exp": 9999999999, **claims}, secreto, algorithm="HS256")


def test_access_token_valido():
    assert decode_token(create_access_token(UID), want="access") == UID


def test_refresh_token_no_sirve_como_access():
    """El bug principal: esto devolvia el user_id y abria la puerta 7 dias."""
    assert decode_token(create_refresh_token(UID), want="access") is None
    # ...pero si se valida como refresh, si funciona.
    assert decode_token(create_refresh_token(UID), want="refresh") == UID


def test_token_firmado_con_otro_secreto_se_rechaza():
    assert decode_token(_firmar({"type": "access"}, "otro-secreto-cualquiera"), want="access") is None


def test_token_sin_tipo_se_rechaza():
    assert decode_token(_firmar({}, settings.jwt_secret), want="access") is None


def test_token_manipulado_se_rechaza():
    # Cambiar el sub invalida la firma.
    tok = create_access_token(UID)
    partes = tok.split(".")
    import base64
    import json as _json

    payload = _json.loads(base64.urlsafe_b64decode(partes[1] + "=="))
    payload["sub"] = "otro-usuario-cualquiera"
    partes[1] = base64.urlsafe_b64encode(_json.dumps(payload).encode()).decode().rstrip("=")
    forrado = ".".join(partes)
    assert decode_token(forrado, want="access") != "otro-usuario-cualquiera"


def test_secreto_actual_difiere_del_placeholder():
    """Si alguien vuelve a poner el valor de ejemplo, el guard de config lo impide;
    esta test es la red de seguridad por si el guard se quita."""
    assert settings.jwt_secret != VIEJO
    assert len(settings.jwt_secret) >= 32