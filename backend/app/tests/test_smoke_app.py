"""Smoke: la app tiene que IMPORTAR.

Por que existe este archivo: los tests de servicios y de repositorio importan
`app.services.*` y `app.models.*`, nunca `app.main`. Un docstring mal indentado
en un router dejo los 146 tests en verde mientras la API no arrancaba: el error
solo aparecia al abrir la app. Un test que importa la raiz lo caza al instante.
"""
import importlib


def test_app_main_importa():
    importlib.import_module("app.main")


def test_todos_los_routers_responden():
    from fastapi.testclient import TestClient

    from app.main import app

    rutas = {r.path for r in app.routes}
    # Si un router dejo de colgar, el prefijo entero desaparece de un jalon y
    # esto avisa mucho antes que un 404 en produccion.
    for esperado in ("/api/v1/auth/login", "/api/v1/asesor/revision",
                     "/api/v1/captura/uso", "/api/v1/movimientos"):
        assert esperado in rutas, f"falta la ruta {esperado}"


def test_openapi_se_genera():
    """El schema se construye al importar los routers; si algo esta roto, truena."""
    from app.main import app

    schema = app.openapi()
    assert schema["info"]["title"]
    assert "/api/v1/auth/login" in schema["paths"]