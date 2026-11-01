import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def _opciones_pool() -> dict:
    """Ajusta el pool al entorno donde corre la API.

    En un servidor tradicional (Docker/Caddy) el pool por defecto de SQLAlchemy
    esta bien. En Vercel cada instancia atiende peticiones concurrentes y hay
    muchas instancias: un pool grande agota las conexiones de Aiven/Neon. Por
    eso en Vercel se limita a 2 conexiones + 2 de desborde por instancia.

    Se puede afinar con DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT sin
    tocar codigo.
    """
    if not os.getenv("VERCEL"):
        return {"pool_pre_ping": True, "pool_recycle": 300}
    return {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "2")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "2")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "10")),
    }


# Aiven/Neon: el ?sslmode=require va en la URL, psycopg2 lo respeta.
engine = create_engine(settings.database_url, **_opciones_pool())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
