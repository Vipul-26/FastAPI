"""Database layer: async engine, session factory, and FastAPI dependency.

Connection flow:
    .env DATABASE_URL → settings.database_url → create_async_engine() → get_db()
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

_engine_kwargs: dict = {}
if os.getenv("PYTEST_RUNNING"):
    # Fresh connection per request — avoids asyncpg cross-test loop issues.
    _engine_kwargs["poolclass"] = NullPool


# Base class for all SQLAlchemy models (User, Document, etc.)
class Base(DeclarativeBase):
    pass


# Engine manages a pool of connections to PostgreSQL (not one connection per request)
engine = create_async_engine(settings.database_url, **_engine_kwargs)

# Factory that creates AsyncSession objects bound to the engine
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep loaded attributes usable after commit in async code
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields one database session per request.

    Usage in routes: db: AsyncSession = Depends(get_db)
    The session is closed automatically when the request finishes.
    On any exception, the session is rolled back (Step 10.4).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
