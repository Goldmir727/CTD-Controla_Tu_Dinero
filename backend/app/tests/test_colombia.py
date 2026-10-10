"""Vocabulario colombiano: modismos, fechas relativas y quincenas."""
from datetime import date

import pytest

from app.services import colombia as co

HOY = date(2026, 10, 8)


# ---------- normalizacion ----------
def test_normalizar_quita_tildes_y_signos():
    assert co.normalizar("Pagó la energía") == "pago la energia"  # ñ->n es intencional
    assert co.normalizar("Nequi, $18.000") == "nequi   18 000"  # signos y comas -> espacios


# ---------- montos con slang ----------
def test_montos_mil():
    assert [m[0] for m in co.montos_en_texto("gaste 18 mil")] == [18000]


def test_montos_lucas():
    # "lucas" es x1000: 15 lucas = 15.000
    assert [m[0] for m in co.montos_en_texto("me gasté 15 lucas")] == [15000]


def test_montos_millones():
    assert [m[0] for m in co.montos_en_texto("pagué 1.5 millones de arriendo")] == [1_500_000]
    assert [m[0] for m in co.montos_en_texto("2 millones")] == [2_000_000]


def test_punto_es_miles_y_coma_es_decimal():
    # Colombia al reves del ingles. Este parser era la causa de "1.5 millones"
    # becoming 15.000.000.
    assert co._parse_numero("1.500.000") == 1_500_000
    assert co._parse_numero("1,5") == 1.5
    assert co._parse_numero("1.500") == 1500
    assert co._parse_numero("18") == 18
    assert co._parse_numero("") == 0.0


def test_montos_varios_en_una_frase():
    # El caso clave: "18 mil en el almuerzo y 5 mil en un taxi"
    assert [m[0] for m in co.montos_en_texto("Gasté 18 mil en el almuerzo y 5 mil en un taxi")] == [18000, 5000]


def test_monto_sin_multiplicador_no_se_confunde():
    # "5 mil" cuenta, un numero suelto como "de 500 personas" no debe contarse
    # porque no lleva multiplicador.
    assert [m[0] for m in co.montos_en_texto("pagué 900mil de impuestos")] == [900000]
    assert co.montos_en_texto("llego el doctor") == []


# ---------- fechas relativas ----------
def test_fecha_hoy_y_ayer():
    assert co.resolver_fecha("hoy gasté en un corrientazo", HOY) == HOY
    assert co.resolver_fecha("ayer saqué plata", HOY) == date(2026, 10, 7)
    assert co.resolver_fecha("anteayer compré mercado", HOY) == date(2026, 10, 6)


def test_fecha_dia_de_semana():
    # 2026-10-08 es jueves. "el martes" mas reciente fue el 6.
    assert co.resolver_fecha("el martes fui al mercado", HOY) == date(2026, 10, 6)
    assert co.resolver_fecha("viernes pagué la luz", HOY) == date(2026, 10, 2)


def test_fecha_hace_n_dias():
    assert co.resolver_fecha("hace 3 días pagué el arriendo", HOY) == date(2026, 10, 5)
    assert co.resolver_fecha("hace 2 semanas compré algo", HOY) == date(2026, 9, 24)


def test_fecha_mes_pasado():
    assert co.resolver_fecha("el mes pasado recibí la prima", HOY) == date(2026, 9, 30)


def test_fecha_dia_mes_texto():
    assert co.resolver_fecha("el 3 de septiembre", HOY) == date(2026, 9, 3)
    # "el 15" en octubre visto desde el dia 8 CAE A FUTURO, mas alla del margen de
    # un dia: correctamente no se inventa. Con un hoy posterior si resuelve.
    assert co.resolver_fecha("el 15 pagué el recibo", HOY) is None
    assert co.resolver_fecha("el 15 pagué el recibo", date(2026, 10, 20)) == date(2026, 10, 15)
    assert co.resolver_fecha("el 5 pagué el recibo", HOY) == date(2026, 10, 5)


def test_fecha_futura_regresa_al_anio_anterior():
    # "el 15 de marzo" en octubre todavia no llega: debe ser marzo de 2026.
    assert co.resolver_fecha("pagué el 15 de marzo", HOY) == date(2026, 3, 15)


def test_fecha_sin_senal_devuelve_none():
    assert co.resolver_fecha("gasté en comida", HOY) is None
    # "el 15 pagué": "pague" NO es un mes, asi que no debe inventarse una fecha vieja.
    assert co.resolver_fecha("el 28 pagué el arriendo", date(2026, 10, 8)) is None


def test_fecha_manana_acepta_el_margen_de_un_dia():
    # RN-03 tolera 1 dia de margen, asi que "mañana" si es una fecha valida.
    assert co.resolver_fecha("gasté 200 mil mañana", HOY) == date(2026, 10, 9)


def test_fecha_pasado_manana_se_rechaza():
    # 2 dias en el futuro excede el margen: no se adivina.
    assert co.resolver_fecha("gasto pasado mañana", HOY) is None


# ---------- quincenas ----------
def test_quincena_primera():
    q = co.quincena(date(2026, 10, 8))
    assert q["etiqueta"] == "2026-10-Q1"
    assert q["inicio"] == "2026-10-01"
    assert q["fin"] == "2026-10-15"
    assert q["dias_totales"] == 15
    assert q["dias_transcurridos"] == 8
    assert q["dias_restantes"] == 7
    assert q["mitad"] == "primera"


def test_quincena_segunda_31_dias():
    # Octubre tiene 31 dias: la segunda quincena va del 16 al 31, no al 30.
    q = co.quincena(date(2026, 10, 20))
    assert q["etiqueta"] == "2026-10-Q2"
    assert q["fin"] == "2026-10-31"
    assert q["dias_totales"] == 16


def test_quincena_segunda_30_dias():
    q = co.quincena(date(2026, 9, 20))
    assert q["fin"] == "2026-09-30"
    assert q["dias_totales"] == 15


def test_quincena_cambio_de_mes():
    assert co.quincena(date(2026, 10, 31))["etiqueta"] == "2026-10-Q2"
    assert co.quincena(date(2026, 11, 1))["etiqueta"] == "2026-11-Q1"
    assert co.quincena(date(2026, 1, 1))["etiqueta"] == "2026-01-Q1"
    assert co.quincena(date(2027, 1, 1))["anio"] == 2027


def test_etiqueta_quincena_legible():
    assert co.etiqueta_quincena("2026-10-Q1") == "primera quincena de octubre"
    assert co.etiqueta_quincena("2026-02-Q2") == "segunda quincena de febrero"
    assert co.etiqueta_quincena("basura") == "basura"


# ---------- metodos y tipo ----------
def test_metodo_por_texto():
    assert co.metodo_por_texto("gasté en un taxi con Nequi") == "Nequi"
    assert co.metodo_por_texto("pagué con Daviplata") == "Daviplata"
    assert co.metodo_por_texto("saqué en efectivo") == "Efectivo"
    assert co.metodo_por_texto("compré algo") is None


def test_tipo_por_verbo():
    assert co.tipo_por_texto("me pagaron la quincena") == "ingreso"
    assert co.tipo_por_texto("me llegó la prima") == "ingreso"
    assert co.tipo_por_texto("pagué el arriendo") == "gasto"
    assert co.tipo_por_texto("compré mercado") == "gasto"
    # Ambiguo: sin verbo claro no se decide, y el modelo lo resuelve.
    assert co.tipo_por_texto("mercado 80 mil") is None