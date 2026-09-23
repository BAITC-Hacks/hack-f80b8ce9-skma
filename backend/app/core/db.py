from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for ORM models. Import models before `create_tables()` runs."""


def _engine_options(url: str) -> dict:
    # In-memory SQLite (tests) must share one connection, or every session sees an empty DB.
    if url.startswith("sqlite"):
        return {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


# The engine connects lazily, so importing this module does not need a running database.
engine = create_async_engine(settings.database_url, **_engine_options(settings.database_url))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def create_tables() -> None:
    import app.models  # noqa: F401  registers models on Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
