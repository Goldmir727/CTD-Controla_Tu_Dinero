"""Informe mensual en PDF: el documento que uno se lleva, o manda al contador.

Por que PDF y no solo Excel: el Excel se edita, el PDF se lee y se archiva. Es lo
que el usuario muestra para "miren como estoy" o lo que entrega sin tener que
limpiar una hoja primero.

Todas las cifras salen de services/finanzas.py. Si el PDF calculara por su cuenta,
la app tendria dos versiones de la misma suma y una de las dos estaria mal.

Nada de forecasts disfrazados de hechos: lo que es proyeccion va marcado como
estimacion, porque un PDF es lo que la gente se cree.
"""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from calendar import monthrange

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)
from sqlalchemy import func

from app.models.finance import Category, Transaction
from app.models.goals import Goal, GoalAporte, Recurring
from app.services import colombia as co
from app.services import finanzas as fin
# El formato de dinero no se reimplementa aqui: servicios/formato.py es la unica
# fuente. Duplicarlo fue justo el bug que hizo que el mensaje del chat dijera
# "1,301,667" y la tabla del PDF "$1.301.667" para la misma cifra.
from app.services.formato import dinero as _dinero

TINTA = colors.HexColor("#1B2A4A")
GRIS = colors.HexColor("#64748B")
LINEA = colors.HexColor("#D7DEE8")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _legible(mes: str) -> str:
    try:
        a, m = int(mes[:4]), int(mes[5:7])
        return f"{MESES[m - 1]} de {a}"
    except (ValueError, IndexError):
        return mes


def _estilos() -> dict:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("t", parent=base["Title"], fontSize=20, textColor=TINTA,
                                 spaceAfter=2),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=9.5, textColor=GRIS,
                              alignment=TA_CENTER, spaceAfter=14),
        "h": ParagraphStyle("h", parent=base["Heading2"], fontSize=12.5, textColor=TINTA,
                            spaceBefore=14, spaceAfter=6),
        "caja": ParagraphStyle("c", parent=base["Normal"], fontSize=9),
        "nota": ParagraphStyle("n", parent=base["Normal"], fontSize=7.5, textColor=GRIS,
                              alignment=TA_CENTER),
        "der": ParagraphStyle("d", parent=base["Normal"], fontSize=9, alignment=TA_RIGHT),
        "centro": ParagraphStyle("ce", parent=base["Normal"], fontSize=9, alignment=TA_CENTER),
    }


def _tabla(datos: list[list], anchos: list[float], alineadas: dict | None = None) -> Table:
    t = Table(datos, colWidths=anchos, hAlign="LEFT")
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), TINTA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), TINTA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, LINEA),
    ]
    for col in (alineadas or {}):
        estilo.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(estilo))
    return t


def _cifras(db, usuario, perfil, mes: str, e) -> list:
    """Las cuatro cifras que todo el mundo mira primero."""
    disp = fin.disponible(db, usuario.id, perfil.id)
    totales = fin.total_mes(db, usuario.id, perfil.id, mes)
    ratio = fin.ratio_fijo(db, usuario.id, perfil.id, mes)
    fila = [["Concepto", "Valor"],
            ["Disponible hoy", _dinero(disp["total"])],
            [f"Ingresos de {_legible(mes)}", _dinero(totales["ingresos"])],
            [f"Gastos de {_legible(mes)}", _dinero(totales["gastos"])],
            ["Balance del mes", _dinero(totales["balance_mes"])],
            ["Tasa de ahorro", f"{totales['tasa_ahorro']}%"],
            ["Gastos fijos del mes", _dinero(ratio["gastos_fijos"])],
            ["Gastos variables", _dinero(ratio["gastos_variables"])]]
    return [[Paragraph(str(c), e["caja"]) for c in fila[0]]] + \
           [[Paragraph(fila[i][0], e["caja"]), Paragraph(fila[i][1], e["der"])] for i in range(1, len(fila))]


def _por_categoria(db, usuario, perfil, mes: str, tipo: str, e, limite: int = 12) -> list:
    # El rango se cierra con monthrange, no con un "-31" fijo: en febrero un
    # "2026-02-31" no existe y la comparacion de texto se sale del mes.
    ultimo = monthrange(int(mes[:4]), int(mes[5:7]))[1]
    filas = db.query(Category.nombre, func.sum(Transaction.monto).label("total")).filter(
        Category.id == Transaction.categoria_id,
        Transaction.user_id == usuario.id, Transaction.perfil_id == perfil.id,
        Transaction.tipo == tipo,
        Transaction.fecha >= f"{mes}-01", Transaction.fecha <= f"{mes}-{ultimo:02d}",
    ).group_by(Category.nombre).order_by(func.sum(Transaction.monto).desc()).limit(limite).all()
    total = sum(float(f[1] or 0) for f in filas)
    if not total:
        return []
    tabla = [["Categoría", "Total", "%"]]
    for nombre, monto in filas:
        pct = float(monto or 0) / total * 100
        tabla.append([Paragraph(str(nombre), e["caja"]),
                      Paragraph(_dinero(monto or 0), e["der"]),
                      Paragraph(f"{pct:.1f}%", e["der"])])
    tabla.append([Paragraph("<b>Total</b>", e["caja"]),
                  Paragraph(f"<b>{_dinero(total)}</b>", e["der"]), Paragraph("", e["der"])])
    return tabla


def informe_mensual(db, usuario, perfil, mes: str | None = None) -> tuple[bytes, str]:
    mes = mes or fin.mes_actual()
    e = _estilos()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            # Sin compresion: el PDF es un documento que la gente
                            # archiva, pesa poco igual, y asi el texto se puede
                            # leer y verificar en los tests.
                            pageCompression=0,
                            title=f"CTD {_legible(mes)}", author="Controla tu Dinero")

    hist: list[str] = []

    def pie(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawCentredString(A4[0] / 2, 10 * mm, hist[0])
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    S: list = []
    S.append(Paragraph("Controla tu Dinero", e["titulo"]))
    S.append(Paragraph(f"Informe de {_legible(mes)} · {perfil.nombre} · "
                       f"{usuario.correo}", e["sub"]))

    S.append(Paragraph("Resumen", e["h"]))
    S.append(_tabla(_cifras(db, usuario, perfil, mes, e), [95 * mm, 45 * mm], {1: "RIGHT"}))

    # La quincena connects con la fase D: el PDF no es solo "el mes".
    S.append(Paragraph("Dónde estás hoy", e["h"]))
    from app.services import quincena as qn

    rev = qn.revision(db, usuario.id, perfil.id, date.today())
    S.append(Paragraph(rev["mensaje"], e["caja"]))
    S.append(Spacer(1, 6))
    rev_lineas = [["Quincena", rev["etiqueta_legible"]],
                  ["Día de la quincena", f"{rev['quincena']['dias_transcurridos']} de "
                                         f"{rev['quincena']['dias_totales']}"],
                  ["Gastado en la quincena", _dinero(rev["movimientos"]["gastos"])],
                  ["Fijos que vencen", _dinero(rev["fijos"]["gastos"])],
                  ["Cierre estimado", _dinero(rev["proyeccion"]["saldo_al_cerrar"])]]
    tabla_rev = [[Paragraph(str(c), e["caja"]) for c in rev_lineas[0]]] + \
                [[Paragraph(rev_lineas[i][0], e["caja"]), Paragraph(rev_lineas[i][1], e["der"])]
                 for i in range(1, len(rev_lineas))]
    S.append(_tabla(tabla_rev, [95 * mm, 45 * mm], {1: "RIGHT"}))
    S.append(Paragraph("El cierre estimado proyecta tu ritmo actual y lo fijo que falta; "
                       "no anticipa ingresos ni gastos extraordinarios.",
                       e["nota"]))

    if rev["alertas"]:
        S.append(Paragraph("Alertas", e["h"]))
        for a in rev["alertas"]:
            S.append(Paragraph(f"• {a['mensaje']}", e["caja"]))
            S.append(Spacer(1, 3))

    gastos = _por_categoria(db, usuario, perfil, mes, "gasto", e)
    if gastos:
        S.append(Paragraph("En qué se fue", e["h"]))
        S.append(_tabla(gastos, [80 * mm, 40 * mm, 20 * mm], {1: "RIGHT", 2: "RIGHT"}))

    ingresos = _por_categoria(db, usuario, perfil, mes, "ingreso", e, limite=8)
    if ingresos:
        S.append(Paragraph("De dónde vino", e["h"]))
        S.append(_tabla(ingresos, [80 * mm, 40 * mm, 20 * mm], {1: "RIGHT", 2: "RIGHT"}))

    fijos = [r for r in db.query(Recurring).filter_by(user_id=usuario.id, perfil_id=perfil.id,
                                                      activo=True).all()]
    if fijos:
        S.append(Paragraph("Gastos fijos", e["h"]))
        datos = [["Nombre", "Día", "Frecuencia", "Monto"]]
        for r in sorted(fijos, key=lambda x: -float(x.monto)):
            datos.append([Paragraph(str(r.nombre), e["caja"]),
                          Paragraph(str(r.dia), e["centro"]),
                          Paragraph(str(r.frecuencia), e["centro"]),
                          Paragraph(_dinero(r.monto), e["der"])])
        S.append(_tabla(datos, [70 * mm, 18 * mm, 32 * mm, 30 * mm], {3: "RIGHT"}))

    metas = db.query(Goal).filter_by(user_id=usuario.id, perfil_id=perfil.id).all()
    if metas:
        S.append(Paragraph("Metas", e["h"]))
        datos = [["Meta", "Ahorrado", "Objetivo", "Progreso"]]
        for g in metas:
            aport = sum(float(a.monto) for a in db.query(GoalAporte).filter_by(goal_id=g.id).all())
            obj = float(g.objetivo)
            pct = (aport / obj * 100) if obj else 0
            datos.append([Paragraph(str(g.nombre), e["caja"]),
                          Paragraph(_dinero(aport), e["der"]),
                          Paragraph(_dinero(obj), e["der"]),
                          Paragraph(f"{pct:.0f}%", e["der"])])
        S.append(_tabla(datos, [60 * mm, 30 * mm, 30 * mm, 20 * mm], {1: "RIGHT", 2: "RIGHT", 3: "RIGHT"}))

    S.append(Spacer(1, 18))
    S.append(Paragraph(
        f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')} en CTD. "
        "Las proyecciones son estimaciones, no certificados. Este documento refleja "
        "los movimientos registrados en la app.", e["nota"]))

    hist.append(f"CTD · {perfil.nombre} · generado el "
                f"{datetime.now().strftime('%d/%m/%Y %H:%M')}")
    doc.build(S, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue(), f"CTD-{perfil.nombre}-{mes}.pdf".replace(" ", "-")