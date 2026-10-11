"""Paises: de donde viene el usuario y como ve los numeros.

Lo que se prueba es lo que estaba roto: el formato no dependia del pais, asi que
un usuario de Estados Unidos veia "$1.234.567". Y la moneda sola no puede
arreglarlo, porque COP, USD y MXN comparten el simbolo "$".
"""
import pytest

from app.services import paises
from app.services.formato import dinero, numero_es


def test_el_formato_cambia_segun_el_pais_no_segun_la_moneda():
    """El mismo numero se ve distinto en cada pais."""
    assert numero_es(1800000, 0, "CO") == "1.800.000"
    assert numero_es(1800000, 2, "US") == "1,800,000.00"
    assert numero_es(1800000, 2, "ES") == "1.800.000,00"
    assert numero_es(1800000, 2, "PE") == "1.800.000,00"


def test_el_simbolo_lo_manda_el_pais():
    assert dinero(1800000, "COP", pais="CO") == "$1.800.000"
    assert dinero(1800000, "MXN", pais="MX") == "$1,800,000.00"
    assert dinero(1800000, "USD", pais="US") == "$1,800,000.00"
    assert dinero(1800000, "EUR", pais="ES") == "€1.800.000,00"
    assert dinero(1800000, "PEN", pais="PE") == "S/1.800.000,00"


def test_cop_usd_y_mxn_comparten_simbolo_por_eso_el_pais_es_necesario():
    """Este es el motivo de que exista el campo: la moneda no desambigua.

    Con la moneda sola, pasar de COP a USD no cambia NADA de lo que se ve y el
    ajuste de moneda parece roto.
    """
    assert paises.simbolo_de("CO") == "$"
    assert paises.simbolo_de("US") == "$"
    assert paises.simbolo_de("MX") == "$"
    # Lo que SI cambia es el separador de miles, que es el sintoma visible.
    assert dinero(1800000, "COP", pais="CO") != dinero(1800000, "USD", pais="US")


def test_sin_pais_se_comporta_como_antes():
    """Las llamadas viejas (documentos, PDF) no saben de pais.

    Si esto cambia, el Excel y el PDF de un usuario saldrian con formato
    extranjero sin que nadie lo pidiera.
    """
    assert dinero(1800000, "COP") == "$1.800.000"
    assert dinero(1234.5, "EUR") == "€1.234,50"


def test_la_quincena_es_lo_estructural_no_un_detalle_de_texto():
    """Es lo unico que hace que la app se comporte distinto, no que se lea distinto."""
    assert paises.usa_quincena("CO") is True
    assert paises.usa_quincena("MX") is True
    assert paises.usa_quincena("US") is False
    assert paises.usa_quincena("ES") is False
    assert paises.usa_quincena("BR") is False


def test_un_pais_desconocido_no_rompe():
    assert paises.pais_de("ZZ")["nombre"] == "Colombia"
    assert paises.nombre(None) == "Colombia"
    assert numero_es(1000, 0, "ZZ") == "1.000"


def test_se_deduce_el_pais_del_idioma_del_navegador():
    assert paises.desde_locale("es-MX") == "MX"
    assert paises.desde_locale("en-US") == "US"
    assert paises.desde_locale("pt-BR") == "BR"
    # 'es' a secas NO es España: casi todos los navegadores en espanol envian
    # solo 'es', y leerlo como la region lo mandaba a España.
    assert paises.desde_locale("es") == "CO"
    assert paises.desde_locale("es-CO") == "CO"
    assert paises.desde_locale("fr-FR") is None
    assert paises.desde_locale("") is None


def test_cada_moneda_apuntaba_a_un_pais_para_migrar_los_existentes():
    """La migracion 0016 relleno el pais desde la moneda: solo por eso es valido."""
    assert paises.MONEDA_A_PAIS["COP"] == "CO"
    assert paises.MONEDA_A_PAIS["MXN"] == "MX"
    assert paises.MONEDA_A_PAIS["USD"] == "US"
    assert paises.MONEDA_A_PAIS["EUR"] == "ES"
    for m, p in paises.MONEDA_A_PAIS.items():
        assert paises.pais_de(p)["moneda"] == m, f"{m} no apunta a un pais con esa moneda"


def test_el_catalogo_esta_bien_ordenado_y_no_tiene_ruinas():
    cat = paises.catalogo()
    assert len(cat) >= 8
    assert [c["nombre"] for c in cat] == sorted(c["nombre"] for c in cat)
    for c in cat:
        assert c["simbolo"] and c["moneda"] and c["nombre"]