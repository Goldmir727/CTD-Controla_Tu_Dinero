"""Paises: de donde viene el usuario y como se formatea su plata.

Por que existe: la app nacio para Colombia, y se nota en todas partes. Se razona
en quincenas (1-15 y 16-30), que es como se cobra aca pero no en todos los paises;
y se formatea SIEMPRE con separador es-CO, asi que un usuario de Estados Unidos
ve "$1.234.567" donde deberia ver "$1,234,567".

Ojo con la trampa de la moneda sola: COP, USD y MXN comparten el simbolo "$". Con
solo el codigo de moneda, cambiar de COP a USD no cambia NADA de lo que se ve, y
el ajuste de moneda parece roto. El pais es lo que desambigua.

`usa_quincena` es el dato estructural: decide si la pantalla de Inicio habla de
quincenas o de semanas. Es la unica parte de la app que cambia de forma, y por
eso vale la pena tenerlo explicito en vez de suponer que todos cobran quincena.
"""
from __future__ import annotations

# sep_miles / sep_decimal: el separador NO se deduce del locale. Comprobado con
# Intl: es-MX usa coma (1,800,000.50) y es-PE usa punto (1.800.000,50), y las dos
# son espanol. Cualquier heuristica del tipo "si es en-US usa coma" se equivoca
# en estos dos paises, que son justamente los que importan.
PAISES: dict[str, dict] = {
    "CO": {"nombre": "Colombia", "moneda": "COP", "simbolo": "$", "decimales": 0,
           "locale": "es-CO", "usa_quincena": True, "idioma": "es",
           "sep_miles": ".", "sep_dec": ","},
    "MX": {"nombre": "México", "moneda": "MXN", "simbolo": "$", "decimales": 2,
           "locale": "es-MX", "usa_quincena": True, "idioma": "es",
           "sep_miles": ",", "sep_dec": "."},
    "US": {"nombre": "Estados Unidos", "moneda": "USD", "simbolo": "$", "decimales": 2,
           "locale": "en-US", "usa_quincena": False, "idioma": "en",
           "sep_miles": ",", "sep_dec": "."},
    "AR": {"nombre": "Argentina", "moneda": "ARS", "simbolo": "$", "decimales": 2,
           "locale": "es-AR", "usa_quincena": True, "idioma": "es",
           "sep_miles": ".", "sep_dec": ","},
    "CL": {"nombre": "Chile", "moneda": "CLP", "simbolo": "$", "decimales": 0,
           "locale": "es-CL", "usa_quincena": False, "idioma": "es",
           "sep_miles": ".", "sep_dec": ","},
    "PE": {"nombre": "Perú", "moneda": "PEN", "simbolo": "S/", "decimales": 2,
           "locale": "es-PE", "usa_quincena": False, "idioma": "es",
           "sep_miles": ".", "sep_dec": ","},
    "EC": {"nombre": "Ecuador", "moneda": "USD", "simbolo": "$", "decimales": 2,
           "locale": "es-EC", "usa_quincena": False, "idioma": "es",
           "sep_miles": ".", "sep_dec": ","},
    "ES": {"nombre": "España", "moneda": "EUR", "simbolo": "€", "decimales": 2,
           "locale": "es-ES", "usa_quincena": False, "idioma": "es",
           "sep_miles": ".", "sep_dec": ","},
    "BR": {"nombre": "Brasil", "moneda": "BRL", "simbolo": "R$", "decimales": 2,
           "locale": "pt-BR", "usa_quincena": False, "idioma": "pt",
           "sep_miles": ".", "sep_dec": ","},
}

# Se deja el catalogo abierto para no tener que desplegar una release cada vez
# que alguien pregunta por su pais, pero lo que se ofrece es lo de arriba.
DEFAULT = "CO"

# De codigo de moneda a pais, para los que ya tienen cuenta y no han elegido.
MONEDA_A_PAIS = {"COP": "CO", "MXN": "MX", "USD": "US", "ARS": "AR",
                 "CLP": "CL", "PEN": "PE", "EUR": "ES", "BRL": "BR"}


def existe(pais: str | None) -> bool:
    return (pais or "").upper() in PAISES


def pais_de(pais: str | None) -> dict:
    """Datos del pais, con Colombia como reserva si llega algo desconocido."""
    return PAISES.get((pais or DEFAULT).upper(), PAISES[DEFAULT])


def nombre(pais: str | None) -> str:
    return pais_de(pais)["nombre"]


def moneda_de(pais: str | None) -> str:
    return pais_de(pais)["moneda"]


def simbolo_de(pais: str | None, moneda: str | None = None) -> str:
    """El simbolo sale del PAIS, no de la moneda.

    Asi es como se arregla el problema de COP y USD sharing the same "$": si el
    usuario esta en Estados Unidos, el simbolo es el de USD aunque por error
    guardara COP.
    """
    return pais_de(pais)["simbolo"]


def locale_de(pais: str | None, moneda: str | None = None) -> str:
    return pais_de(pais)["locale"]


def decimales_de(pais: str | None, moneda: str | None = None) -> int:
    return int(pais_de(pais)["decimales"])


def separadores(pais: str | None) -> tuple[str, str]:
    """(separador de miles, separador decimal) del pais."""
    p = pais_de(pais)
    return p["sep_miles"], p["sep_dec"]


def usa_quincena(pais: str | None) -> bool:
    """True si en ese pais tiene sentido trabajar por quincenas."""
    return bool(pais_de(pais)["usa_quincena"])


def catalogo() -> list[dict]:
    """Para el selector de Ajustes."""
    return [{"codigo": k, "nombre": v["nombre"], "moneda": v["moneda"],
             "simbolo": v["simbolo"], "usa_quincena": v["usa_quincena"]}
            for k, v in sorted(PAISES.items(), key=lambda kv: kv[1]["nombre"])]


def desde_locale(tag: str | None) -> str | None:
    """Deduce el pais del idioma del navegador (ej: 'es-MX' -> 'MX').

    Es lo mejor que se puede hacer sin pedir permisos ni llamar a un servicio de
    geolocalizacion por IP. Un usuario que viaja no la tendria bien, y por eso
    siempre es editable y nunca se cambia solo despues del registro.
    """
    if not tag:
        return None
    partes = tag.split("-")
    # La region solo existe si el tag la trae. Sin esta comprobacion, un "es" a
    # secas se leia como "ES" (España) y no como "español sin pais": casi todos
    # los navegadores en español envian solo "es".
    if len(partes) > 1:
        region = partes[-1].upper()
        if region in PAISES:
            return region
    if tag.lower().startswith("es"):
        return DEFAULT
    return None