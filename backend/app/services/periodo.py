"""Periodo de revision: mes o quincena, segun lo que elija el usuario.

Por que existe: la quincena (1-15 / 16-fin) es la unidad de vida financiera de
quien cobra asi, pero encerraba la app para el resto. Antes, `quincena.revision`
cortaba SIEMPRE por quincena sin mirar ni el pais ni al usuario, y `usa_quincena`
solo cambiaba el texto del tour: un usuario de Estados Unidos veia "primera
quincena, dia 12 de 15" sobre una mathematics que no era suya.

Aqui vive la eleccion. El motor siempre es real: si el usuario pide mes, el
periodo va del dia 1 al ultimo del mes y la proyeccion se reparte sobre los dias
reales de ese mes. Nunca se cambia la etiqueta y se deja el corte por quincena,
porque eso daria numeros que no cuadran con lo que dice la pantalla.

El formato del diccionario es el mismo que `colombia.quincena` (etiqueta, inicio,
fin, dias_transcurridos, dias_totales...) para que los dos caminos sirvan al
mismo render.
"""
from calendar import monthrange
from datetime import date, timedelta

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def mes(fecha: date | None = None) -> dict:
    """El mes completo de `fecha`, del dia 1 al ultimo."""
    f = fecha or date.today()
    ultimo = monthrange(f.year, f.month)[1]
    inicio, fin = date(f.year, f.month, 1), date(f.year, f.month, ultimo)
    transcurridos = min(f.day, ultimo)
    return {"etiqueta": f"{f.year}-{f.month:02d}",
            "anio": f.year, "mes": f.month, "numero": 0,
            "inicio": inicio.isoformat(), "fin": fin.isoformat(),
            "dias_totales": ultimo, "dias_transcurridos": transcurridos,
            "dias_restantes": max(ultimo - transcurridos, 0),
            "mitad": "mes", "usa_quincena": False}


def periodo(fecha: date | None = None, usa_quincena: bool = False) -> dict:
    """El periodo que le toca al usuario: quincena o mes."""
    if usa_quincena:
        from app.services import colombia as co
        q = co.quincena(fecha)
        q["usa_quincena"] = True
        return q
    return mes(fecha)


def etiqueta_periodo(etiqueta: str, usa_quincena: bool) -> str:
    """'2026-10' -> 'octubre de 2026'; '2026-10-Q1' -> 'primera quincena de octubre'."""
    if usa_quincena:
        from app.services import colombia as co
        return co.etiqueta_quincena(etiqueta)
    try:
        anio, mes_ = etiqueta.split("-")
        return f"{MESES[int(mes_) - 1]} de {anio}"
    except (ValueError, IndexError):
        return etiqueta


def nombre_mes(numero: int) -> str:
    try:
        return MESES[numero - 1]
    except IndexError:
        return str(numero)


def periodo_anterior(q: dict, usa_quincena: bool) -> dict | None:
    """El mismo periodo del mes anterior, para comparar como con como.

    En quincena hay que conservar el numero: comparar la segunda contra la primera
    daria siempre "gastaste menos", porque la segunda siempre tiene menos dias.
    En mes es simplemente el mes previo.
    """
    f_ini = date.fromisoformat(q["inicio"])
    ultimo_dia_mes_anterior = f_ini.replace(day=1) - timedelta(days=1)
    if not usa_quincena:
        return mes(date(ultimo_dia_mes_anterior.year, ultimo_dia_mes_anterior.month, 1))
    dia_equivalente = 1 if q.get("numero") == 1 else 16
    return periodo(date(ultimo_dia_mes_anterior.year, ultimo_dia_mes_anterior.month,
                         dia_equivalente), usa_quincena=True)