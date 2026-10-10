"""Excel canonico y PDF: como el usuario saca sus datos y se lleva un documento.

Excel es el formato que la gente usa de verdad (y el que un contador pide), asi
que es GRATIS. Cobrarlo no era un negocio: el JSON de /respaldo entrega lo mismo
y se abre en Bloc de Notas, asi que el candado era evitable por cualquiera y
solo decia "te cobramos por tus datos".

El PDF si es de PRO, y por una razon concreta: no es una copia de los datos sino
un documento armado (resumen, quincena, alertas, desglose) pensado para
ensenarselo a otro. Eso si es un producto.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.core.database import get_db
from app.core.deps import get_current_user, get_perfil
from app.core.plan import require_plan
from app.models.perfil import Perfil
from app.models.user import User
from app.services import documentos as docs
from app.services import pdf as pdf_svc

router = APIRouter(tags=["documentos"])


@router.get("/documentos/excel")
def excel(
    perfil_id: str | None = Query(default=None, description="Si se omite, sale todo"),
    db=Depends(get_db), user: User = Depends(get_current_user),
):
    """Descarga el respaldo en Excel, con las hojas que el usuario puede leer.

    Sin candado y sin cuota: esto es el respaldo del usuario. Si el proposito de
    cobro fuera cobrar la informacion, seria para cobrar la app entera.
    """
    try:
        contenido = docs.exportar_excel(db, user, [perfil_id] if perfil_id else None)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"No se pudo armar el Excel: {e}")
    nombre = f"ctd-{perfil_id or 'todo'}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f"attachment; filename=ctd.xlsx; filename*=UTF-8''{quote(nombre)}"},
    )


@router.post("/documentos/importar-excel")
async def importar_excel(
    archivo: UploadFile = File(...),
    db=Depends(get_db), user: User = Depends(get_current_user),
):
    """Restaura un .xlsx. Es idempotente: subirlo dos veces no duplica nada."""
    crudo = await archivo.read()
    if not crudo:
        raise HTTPException(422, "El archivo vino vacio")
    try:
        payload = docs.leer_excel(crudo)
    except docs.ErrorExcel as e:
        # El mensaje va tal cual al usuario: explica que esta mal, sin jerga.
        raise HTTPException(422, str(e))
    return docs.importar_excel(db, user, payload)


@router.get("/documentos/reporte.pdf")
def reporte_pdf(
    mes: str | None = Query(default=None, description="aaa-mm; por defecto, el actual"),
    db=Depends(get_db), user: User = Depends(get_current_user),
    perfil: Perfil = Depends(get_perfil),
    _pro: User = Depends(require_plan(
        "export_pdf", "El informe en PDF es una función PRO. Activa tu plan "
                      "para descargarlo.")),
):
    """Informe del mes en PDF. Es de PRO: esto es lo que se paga."""
    try:
        contenido, nombre = pdf_svc.informe_mensual(db, user, perfil, mes)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"No se pudo armar el PDF: {e}")
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition":
                 f"attachment; filename=informe.pdf; filename*=UTF-8''{quote(nombre)}"},
    )