"""Motor de calculo: rutas de ahorro y funciones puras de finanzas.py.

Estas cifras son las que el asesor IA devuelve via function calling, asi que un
error aqui es un error que el chatbot le dice al usuario.
"""
from datetime import date

from app.services import finanzas as fin

HOY = date(2026, 10, 8)


def test_ruta_meta_meses_redondeo_arriba():
    # 300.000 / 50.000 = 6 exactos
    r = fin.ruta_meta_desde_faltante(300000, 50000, hoy=HOY)
    assert r["meses"] == 6
    assert r["alcanzable"] is True


def test_ruta_meta_no_fracciona_meses():
    # 300.000 / 50.000 = 6 exactos; 250.000 / 50.000 = 5
    assert fin.ruta_meta_desde_faltante(250000, 50000, hoy=HOY)["meses"] == 5
    # 100.000 / 30.000 = 3.33 -> debe decir 4, nunca 3
    assert fin.ruta_meta_desde_faltante(100000, 30000, hoy=HOY)["meses"] == 4


def test_ruta_meta_sin_aporte_no_es_alcanzable():
    r = fin.ruta_meta_desde_faltante(300000, 0, hoy=HOY)
    assert r["alcanzable"] is False
    assert r["meses"] is None
    assert r["requerido_mensual"] is None
    assert "aporte 0" in r["razon"]


def test_ruta_meta_avisa_si_no_llega_a_la_fecha():
    # objetivo en 9 meses (junio 2027 desde octubre 2026), faltante 1.200.000.
    # Aportando 100.000/mes hacen falta 12 > 9: no alcanza y debe sugerir el aporte.
    r = fin.ruta_meta_desde_faltante(1200000, 100000, date(2027, 6, 30), HOY)
    assert r["meses"] == 12
    assert r["meses_hasta_fecha"] == 9
    assert r["alcanza_en_fecha"] is False
    assert r["requerido_mensual"] == 133333.33  # 1.200.000 / 9
    assert "llegar a tiempo" in r["razon"]


def test_ruta_meta_alcanza_si_el_aporte_alcanza():
    r = fin.ruta_meta_desde_faltante(1200000, 200000, date(2027, 6, 30), HOY)
    assert r["meses"] == 6
    assert r["meses_hasta_fecha"] == 9
    assert r["alcanza_en_fecha"] is True
    assert "requerido_mensual" not in r  # no hay que sugerir nada


def test_ruta_meta_sin_fecha_no_opina_sobre_plazos():
    r = fin.ruta_meta_desde_faltante(300000, 50000, None, HOY)
    assert r["meses"] == 6
    assert "meses_hasta_fecha" not in r


def test_todo_proyeccion_va_marcada_como_estimacion():
    # RN-07: todo predictivo se etiqueta.
    r = fin.ruta_meta_desde_faltante(300000, 50000, hoy=HOY)
    assert r["estimacion"] is True


def test_frecuencias_normalizadas_a_mes():
    assert fin.FACTOR_FRECUENCIA["mensual"] == 1.0
    assert fin.FACTOR_FRECUENCIA["quincenal"] == 2.0
    assert round(45000 * fin.FACTOR_FRECUENCIA["quincenal"]) == 90000


def test_mes_siguiente_rota_el_ano():
    assert fin._mes_siguiente("2026-12") == "2027-01"
    assert fin._mes_siguiente("2026-01") == "2026-02"


def test_meses_hacia_atras_rota_el_ano():
    assert fin._meses_hacia_atras("2026-01", 3) == ["2026-01", "2025-12", "2025-11"]
