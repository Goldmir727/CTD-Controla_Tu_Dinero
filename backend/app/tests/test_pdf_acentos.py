"""Los acentos en el PDF.

Un PDF donde "Comida" aparece como "Comid?" o "Nómina" como "N?mina" no sirve
para mandarlo al contador: es el documento que el usuario enseña fuera de la
app, y si se ve roto la app se ve rota.

reportlab escribe los bytes acentuados como escapes octales dentro del literal
("N\\363mina"), asi que un test que busque el byte crudo dara falso negativo
aunque el PDF este perfecto. Por eso el test tambien verifica el escapado.
"""
import re
from io import BytesIO

from reportlab.platypus import Paragraph, SimpleDocTemplate

from app.services import pdf as pdf_svc

ESPANOL = "áéíóúñÁÉÍÓÚÑ¿¡"
WINANSI = {
    "á": 0xE1, "é": 0xE9, "í": 0xED, "ó": 0xF3, "ú": 0xFA, "ñ": 0xF1,
    "Á": 0xC1, "É": 0xC9, "Í": 0xCD, "Ó": 0xD3, "Ú": 0xDA, "Ñ": 0xD1,
    "¿": 0xBF, "¡": 0xA1,
}


def _pdf_unescape(s: str) -> bytes:
    """Convierte el literal de un PDF a bytes reales.

    Hay que hacerlo porque reportlab escapa todo lo no imprimible y los acentos
    se van como octal: \\363 es la o acentuada (0xF3 en WinAnsi).
    """
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c != "\\":
            out.extend(c.encode("latin-1", "replace"))
            i += 1
            continue
        sig = s[i + 1: i + 2]
        if sig.isdigit():                      # \ddd octal
            out.append(int(s[i + 1: i + 4], 8) & 0xFF)
            i += 4
        elif sig == "n":
            out.append(0x0A); i += 2
        elif sig == "r":
            out.append(0x0D); i += 2
        elif sig == "t":
            out.append(0x09); i += 2
        elif sig in ("(", ")", "\\"):
            out.extend(sig.encode("latin-1")); i += 2
        else:
            out.extend(b"\\"); i += 1
    return bytes(out)


def _texto_del_pdf(contenido: bytes) -> str:
    """Texto legible del PDF, con los acentos ya resueltos."""
    crudo = contenido.decode("latin-1", errors="ignore")
    trozos = re.findall(r"\((.*?)\)\s*Tj", crudo)
    return " ".join(_pdf_unescape(t).decode("cp1252", errors="replace") for t in trozos)


def test_los_acentos_llegan_intactos_al_pdf():
    """El informe se genera sin comprimir justamente para poder verificarlo:
    un PDF comprimido es binario opaco y nadie podria detectar una tilde rota."""
    estilos = pdf_svc._estilos()
    buf = BytesIO()
    SimpleDocTemplate(buf, pageCompression=0).build(
        [Paragraph("Comida Nómina " + ESPANOL, estilos["caja"])])

    legible = _texto_del_pdf(buf.getvalue())
    assert "Comida Nómina áéíóúñÁÉÍÓÚÑ¿¡" in legible, \
        f"los acentos no llegaron al PDF. Salio: {legible!r}"


def test_cada_acento_usa_su_byte_de_winansi():
    """Se comprueba a nivel de BYTE, no de texto.

    Decodificar y comparar strings daria "ok" casi siempre; lo que importa es el
    byte exacto que va a ver el lector de PDF.
    """
    estilos = pdf_svc._estilos()
    buf = BytesIO()
    SimpleDocTemplate(buf, pageCompression=0).build(
        [Paragraph(ch, estilos["caja"]) for ch in ESPANOL])
    crudo = buf.getvalue().decode("latin-1", errors="ignore")

    for ch, cod in WINANSI.items():
        # El byte puede ir crudo o como escape octal de tres digitos.
        raw = chr(cod)
        octal = "\\%03o" % cod
        assert raw in crudo or octal in crudo, (
            f"{ch!r} (0x{cod:02X}) no llego al PDF: el lector mostraria otra letra")


def test_un_caracter_que_la_fuente_no_tiene_no_se_convierte_en_interrogacion():
    """El fallo tipico es silencioso: sale un '?' y nadie se entera hasta que el
    usuario lo lleva al contador."""
    estilos = pdf_svc._estilos()
    buf = BytesIO()
    SimpleDocTemplate(buf, pageCompression=0).build([Paragraph("Café ☕", estilos["caja"])])
    texto = _texto_del_pdf(buf.getvalue())
    assert "Café" in texto, "un caracter no soportado se llevo por delante el texto bueno"
    assert "?" not in texto, "algo se convirtio en interrogacion"