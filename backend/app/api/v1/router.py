from fastapi import APIRouter

from app.api.v1 import (
    asesor,
    auth,
    captura,
    catalogos,
    cuentas,
    documentos,
    movimientos,
    perfiles,
    plan,
    recurrentes,
    reportes,
    resumen,
)

api_router = APIRouter()
for r in (auth.router, perfiles.router, cuentas.router, movimientos.router, plan.router,
          resumen.router, catalogos.router, asesor.router, recurrentes.router,
          reportes.router, captura.router, documentos.router):
    api_router.include_router(r)
