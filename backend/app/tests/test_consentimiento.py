"""Consentimiento legal: el cambio de version tiene que re-preguntar.

Regresion: user_out solo miraba si la fecha existia, nunca la version. Subir la
politica de datos a 1.1 (envio a Groq, Circular 008 SIC) no habria tenido efecto:
nadie volvio a consentir. Y /auth/consentimiento solo rellenaba cuando la fecha
era nula, asi que el ConsentBanner habria aparecido para siempre sin poder
cerrarse.
"""
from datetime import datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.core.legal import DATOS_VERSION, TERMINOS_VERSION
from app.schemas.auth import user_out


@pytest.fixture()
def usuario():
    db = SessionLocal()
    from app.models.user import User

    u = User(nombre="Consent", correo="consent_test_%d@example.com" % datetime.utcnow().timestamp().__hash__(),
             password_hash="x", moneda="COP",
             acepta_terminos_at=datetime.utcnow(), terminos_version=TERMINOS_VERSION,
             acepta_datos_at=datetime.utcnow(), datos_version=DATOS_VERSION)
    db.add(u)
    db.commit()
    db.refresh(u)
    yield u
    db.delete(u)
    db.commit()
    db.close()


def test_consentimiento_vigente_cuenta_como_aceptado(usuario):
    out = user_out(usuario)
    assert out.acepta_terminos is True
    assert out.acepta_datos is True


def test_version_vieja_deja_de_contar(usuario):
    """El caso real: el usuario acepto la 1.0, subimos a 1.1."""
    usuario.datos_version = "1.0"
    assert user_out(usuario).acepta_datos is False
    # Y el re-registro del consentimiento lo vuelve a poner en true.
    usuario.datos_version = DATOS_VERSION
    assert user_out(usuario).acepta_datos is True


def test_sin_fecha_no_acepta(usuario):
    usuario.acepta_datos_at = None
    assert user_out(usuario).acepta_datos is False


def test_terminos_tambien_siguen_la_version(usuario):
    usuario.terminos_version = "0.9"
    assert user_out(usuario).acepta_terminos is False


def test_la_version_de_datos_actual_menciona_la_ia():
    """Guarda contra regresiones: si esto vuelve a 1.0, el aviso de la Circular 008
    se pierde y la app vuelve a enviar datos a Groq sin volver a preguntar."""
    assert DATOS_VERSION == "1.1"