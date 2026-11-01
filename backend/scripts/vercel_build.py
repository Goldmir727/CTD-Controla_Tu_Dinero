"""Build de la API en Vercel: instala dependencias (lo hace Vercel) y migra.

Las migraciones se aplican solo en produccion o cuando RUN_MIGRATIONS=1. Un
Preview no debe tocar la base real: si un preview corre con el esquema viejo,
mejor que falle ahi y no que borre/altere datos de produccion.

Si DATABASE_URL no esta configurada, el build falla con un mensaje claro en vez
de desplegar una API que no puede conectarse.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def log(msg: str) -> None:
    print(f"[vercel-build] {msg}", flush=True)


def main() -> int:
    entorno = os.getenv("VERCEL_ENV", "")
    forzar = os.getenv("RUN_MIGRATIONS", "").strip().lower() in {"1", "true", "yes"}

    if entorno != "production" and not forzar:
        log(f"VERCEL_ENV={entorno or 'local'}: no se aplican migraciones.")
        return 0

    if not (os.getenv("DATABASE_URL") or "").strip():
        log("ERROR: DATABASE_URL no esta configurada; no puedo aplicar migraciones.")
        return 1

    log("Aplicando migraciones: alembic upgrade head")
    return subprocess.call(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(RAIZ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
