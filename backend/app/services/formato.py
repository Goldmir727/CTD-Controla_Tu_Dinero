"""Formato de numeros y dinero (es-CO) para API, Excel y PDF.

Por que existe: el frontend tiene `fmt` duplicado en 7 vistas con el simbolo `$`
hardcodeado (elegir EUR renderizaba "$"), y el asesor IA inventaba simbolos porque
el contexto nunca le decia la moneda del usuario. Esta es la unica fuente.

Se implementa a mano (no `locale`) para no depender de locales del sistema en la
imagen python:3.12-slim.
"""
import re

MONEDAS: dict[str, dict[str, str]] = {
    "COP": {"simbolo": "$", "nombre": "pesos colombianos", "decimales": "0"},
    "USD": {"simbolo": "$", "nombre": "dólares", "decimales": "0"},
    "MXN": {"simbolo": "$", "nombre": "pesos mexicanos", "decimales": "0"},
    "EUR": {"simbolo": "€", "nombre": "euros", "decimales": "2"},
}


def simbolo_moneda(codigo: str) -> str:
    return MONEDAS.get((codigo or "").upper(), MONEDAS["COP"])["simbolo"]


def nombre_moneda(codigo: str) -> str:
    return MONEDAS.get((codigo or "").upper(), MONEDAS["COP"])["nombre"]


def decimales_moneda(codigo: str) -> int:
    return int(MONEDAS.get((codigo or "").upper(), MONEDAS["COP"])["decimales"])


def numero_es(valor: float | int | None, decimales: int = 0, pais: str | None = None) -> str:
    """1234567.89 -> '1.234.567,89' en Colombia, '1,234,567.89' en Estados Unidos.

    El separador lo da el PAIS y viene explicito en el catalogo, no deducido del
    locale: es-MX usa coma y es-PE usa punto, y las dos son espanol. Adivinar por
    el locale las equivoca justo en los paises que mas importan.
    """
    v = float(valor or 0)
    neg = v < 0
    s = f"{abs(v):,.{decimales}f}"
    entero, _, frac = s.partition(".")
    if pais:
        from app.services import paises

        sep_m, sep_d = paises.separadores(pais)
    else:
        sep_m, sep_d = ".", ","
    entero = entero.replace(",", sep_m)
    out = entero + (sep_d + frac if frac else "")
    return f"-{out}" if neg else out


def dinero(valor: float | int | None, moneda: str = "COP", decimales: int | None = None,
           pais: str | None = None) -> str:
    """1800000 en Colombia -> '$1.800.000'; en Estados Unidos -> '$1,800,000.00'.

    Sin `pais` se comporta como antes: simbolo y formato salen de la MONEDA. Es
    lo que necesitan las llamadas viejas y las que no saben de pais (los
    documentos, el PDF). Con pais, el pais manda sobre los dos.
    """
    from app.services import paises

    if pais:
        sim = paises.simbolo_de(pais, moneda)
        dec = decimales if decimales is not None else paises.decimales_de(pais, moneda)
    else:
        sim = simbolo_moneda(moneda)
        dec = decimales if decimales is not None else decimales_moneda(moneda)
    return f"{sim}{numero_es(valor, dec, pais)}"


def porcentaje(valor: float | None, decimales: int = 1) -> str:
    return f"{numero_es(valor, decimales)}%"


def fecha_es(fecha) -> str:
    """'2026-10' -> 'octubre 2026'; '2026-10-08' -> '8 de octubre de 2026'."""
    if fecha is None:
        return ""
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    try:
        if len(str(fecha)) == 7:
            a, m = str(fecha).split("-")
            return f"{meses[int(m) - 1]} {a}"
        d = str(fecha)
        return f"{int(d[8:10])} de {meses[int(d[5:7]) - 1]} de {d[0:4]}"
    except (ValueError, IndexError):
        return str(fecha)


# Espacios que usan los formateadores de numero (U+202F fino, U+00A0, U+2009 fino,
# U+2007) y que en prosa espanola casi no aparecen. Medido: gpt-oss devuelve
# "1 480 000" con U+202F, mientras el resto de la app usa "1.780.000".
# OJO: tambien mete espacio fino entre palabra y numero ("12 meses", "junio 2027"),
# por eso el punto solo se inserta cuando el espacio cae ENTRE DIGITOS.
_ESPACIOS_NUMERICOS = "\u202f\u00a0\u2009\u2007"
_SEP_ENTRE_DIGITOS = re.compile(r"(\d)([" + _ESPACIOS_NUMERICOS + r"])(\d)")
_CUALQUIER_ESPACIO_EXOTICO = re.compile("[" + _ESPACIOS_NUMERICOS + "]")


def normalizar_numeros(texto: str) -> str:
    """Convierte los separadores de miles del modelo al formato de la app.

    "1 480 000" -> "1.480.000"   (U+202F entre digitos: grupos 1 y 3)
    "12 meses"  -> "12 meses"    (U+202F entre digito y letra: no se inserta punto)
    Se itera porque "1 480 000" lleva dos separadores.
    """
    if not texto:
        return texto
    out = texto
    for _ in range(4):  # 4 pasadas alcanzan para 999.999.999
        nuevo = _SEP_ENTRE_DIGITOS.sub(r"\1.\3", out)
        if nuevo == out:
            break
        out = nuevo
    # Los exoticos que sobran (entre palabra y numero) se vuelven espacio normal
    # para que se vean como el resto del texto.
    return _CUALQUIER_ESPACIO_EXOTICO.sub(" ", out)
