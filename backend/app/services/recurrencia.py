"""Cuando cae un fijo, de verdad.

Por que existe: `recurrings.dia` es un dia del mes (1-31), y con eso solo se
puede decir "el 20 de cada mes". Un pago que cae cada domingo no es un dia del
mes: es un dia de la semana, y anclarlo al 18 hace que el mes siguiente caiga en
miercoles. Ademas el conteo reiniciaba en cada mes, asi que un semanal anclado
tarde aparecia dos veces en el mes (18 y 25) en vez de las cuatro o cinco que
tiene de verdad, y un quincenal con dia > 15 perdia la segunda ocurrencia.

Aqui vive la unica respuesta a "¿que dias cae este fijo entre estas fechas?".
La usan la revision del periodo (dashboard), el listado de fijos y la captura.
Si cada pantalla lo calculara por su cuenta, una de las dos mentiria.
"""
from calendar import monthrange
from datetime import date, timedelta

from app.services.colombia import DIAS_SEMANA

# 0 = lunes ... 6 = domingo (el mismo orden que date.weekday()).
NOMBRES_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

FRECUENCIAS = ("mensual", "quincenal", "semanal")


def _meses(desde: date, hasta: date):
    y, m = desde.year, desde.month
    while (y, m) <= (hasta.year, hasta.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def ocurrencias(desde: date, hasta: date, frecuencia: str, dia: int,
                dia_semana: int | None = None) -> list[date]:
    """Las fechas en que cae el fijo dentro de [desde, hasta].

    - mensual: el dia `dia` de cada mes; en meses cortos cae el ultimo dia
      (un arriendo del 30 se cobra el 28 de febrero, no desaparece).
    - quincenal: dos veces al mes, a 15 dias de distancia. Si el dia elegido
      pasa de 15 (el 20), la pareja es 5 y 20; antes el 35 no existia y la
      segunda quincena se perdia.
    - semanal con `dia_semana`: cae exactamente una vez cada 7 dias, siempre el
      mismo dia de la semana. Es el caso de "me pagan cada domingo".
    - semanal sin `dia_semana` (fijos viejos): cada 7 dias alrededor del dia
      elegido, para que no se pierda ninguna semana del mes.
    """
    if desde > hasta:
        return []
    if frecuencia == "semanal" and dia_semana is not None and 0 <= int(dia_semana) <= 6:
        primera = desde + timedelta(days=(int(dia_semana) - desde.weekday()) % 7)
        out = []
        d = primera
        while d <= hasta:
            out.append(d)
            d += timedelta(days=7)
        return out

    fechas: set[date] = set()
    for y, m in _meses(desde, hasta):
        ultimo = monthrange(y, m)[1]
        base = date(y, m, min(max(int(dia or 1), 1), ultimo))
        if frecuencia == "mensual":
            fechas.add(base)
        elif frecuencia == "quincenal":
            otro = base - timedelta(days=15) if base.day > 15 else base + timedelta(days=15)
            if otro.month != m:
                otro = date(y, m, ultimo)
            fechas.update({base, otro})
        elif frecuencia == "semanal":
            for k in range(-4, 5):
                d = base + timedelta(days=7 * k)
                if d.month == m:
                    fechas.add(d)
    return sorted(f for f in fechas if desde <= f <= hasta)


def proxima(desde: date, frecuencia: str, dia: int,
            dia_semana: int | None = None) -> date | None:
    """La siguiente vez que cae el fijo, desde `desde` (inclusive)."""
    fechas = ocurrencias(desde, desde + timedelta(days=400), frecuencia, dia, dia_semana)
    return fechas[0] if fechas else None


def etiqueta(frecuencia: str, dia: int, dia_semana: int | None = None) -> str:
    """Como se lee el fijo en voz alta: "cada domingo", "el 20 y el 5"."""
    if frecuencia == "semanal":
        if dia_semana is not None and 0 <= int(dia_semana) <= 6:
            return f"cada {NOMBRES_DIA[int(dia_semana)]}"
        return f"cada 7 días desde el {dia}"
    if frecuencia == "quincenal":
        d = int(dia)
        return f"el {d} y el {d - 15 if d > 15 else d + 15} de cada mes"
    return f"el día {dia} de cada mes"

