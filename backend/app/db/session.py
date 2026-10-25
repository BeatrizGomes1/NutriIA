"""Mecanismo e fábrica de sessões do banco, compartilhados pelos serviços e pelo futuro FastAPI."""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings


def sqlalchemy_url(database_url: str) -> URL:
    """Adapta a URL do Prisma ao psycopg e remove opções exclusivas do Prisma."""
    url = make_url(database_url)
    query = dict(url.query)
    query.pop("schema", None)
    drivername = "postgresql+psycopg" if url.drivername in {"postgres", "postgresql"} else url.drivername
    return url.set(drivername=drivername, query=query)


def create_session_factory(database_url: str):
    engine = create_engine(sqlalchemy_url(database_url), pool_pre_ping=True)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_session_factory(database_url)
