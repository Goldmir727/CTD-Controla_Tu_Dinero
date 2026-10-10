from fastapi import APIRouter

from app.api.v1 import (
    asesor,
    auth,
    catalogos,
    cuentas,
    movimientos,
    plan,
    recurrentes,
    reportes,
    resumen,
)

api_router = APIRouter()
for r in (auth.router, cuentas.router, movimientos.router, plan.router,
          resumen.router, catalogos.router, asesor.router, recurrentes.router,
          reportes.router):
    api_router.include_router(r)
