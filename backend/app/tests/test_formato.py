"""Formato de numeros/dinero y normalizacion de la respuesta del asesor.

Regresion: gpt-oss devuelve separadores de miles con U+202F ("1 480 000") y tambien
los usa entre palabra y numero ("12 meses"). La app usa "1.780.000", asi que hay
que convertir solo los que van entre digitos.
"""
from app.services.formato import (
    dinero,
    fecha_es,
    normalizar_numeros,
    numero_es,
    porcentaje,
    simbolo_moneda,
)

NNBSP = "\u202f"
NBSP = "\u00a0"


def test_normalizar_separador_de_miles_fino():
    assert normalizar_numeros(f"1{NNBSP}480{NNBSP}000") == "1.480.000"
    assert normalizar_numeros(f"gastaste 500{NNBSP}000 COP") == "gastaste 500.000 COP"
    assert normalizar_numeros(f"1{NBSP}200{NBSP}000 y 12{NBSP}meses") == "1.200.000 y 12 meses"


def test_normalizar_no_toca_punto_ya_puesto():
    assert normalizar_numeros("1.480.000") == "1.480.000"
    assert normalizar_numeros("de 1 a 2") == "de 1 a 2"


def test_normalizar_no_pone_punto_entre_digito_y_palabra():
    # Regresion del bug: una version previa insertaba el punto aqui y producia
    # "12.meses" y "junio.2027".
    assert normalizar_numeros(f"12{NNBSP}meses") == "12 meses"
    assert normalizar_numeros(f"junio{NNBSP}2027") == "junio 2027"


def test_normalizar_casos_limites():
    assert normalizar_numeros("") == ""
    assert normalizar_numeros(None) is None


def test_numero_es_punto_miles_coma_decimal():
    assert numero_es(1234567.89, 2) == "1.234.567,89"
    assert numero_es(1234567.89, 0) == "1.234.568"
    assert numero_es(-45000) == "-45.000"
    assert numero_es(0) == "0"
    assert numero_es(None) == "0"
    assert numero_es(1000000) == "1.000.000"


def test_dinero_usa_el_simbolo_de_la_moneda_del_usuario():
    # El bug original: el simbolo estaba fijo en "$" en toda la app, asi que un
    # usuario EUR veia "$1.234,50".
    assert dinero(1800000, "COP") == "$1.800.000"
    assert dinero(1800000, "USD") == "$1.800.000,00"
    assert dinero(1800000, "MXN") == "$1.800.000,00"
    assert dinero(1234.5, "EUR") == "€1.234,50"
    assert simbolo_moneda("EUR") == "€"
    assert simbolo_moneda("desconocida") == "$"  # no revienta con una moneda rara


def test_porcentaje():
    # 1 decimal por defecto, para que el ancho del texto no salte en la UI.
    assert porcentaje(12.345) == "12,3%"
    assert porcentaje(100) == "100,0%"
    assert porcentaje(100, 0) == "100%"


def test_fecha_es_en_espanol():
    assert fecha_es("2026-10") == "octubre 2026"
    assert fecha_es("2026-10-08") == "8 de octubre de 2026"
    assert fecha_es(None) == ""
