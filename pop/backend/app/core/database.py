"""SQLAlchemy 2.0 asynchronous and synchronous database engine and session managers."""

from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Async engine for FastAPI endpoints
async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development" and settings.LOG_LEVEL == "DEBUG"),
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Synchronous engine for migrations, seeding scripts, and test runners
sync_engine = create_engine(
    settings.DATABASE_SYNC_URL,
    echo=(settings.ENVIRONMENT == "development" and settings.LOG_LEVEL == "DEBUG"),
    future=True,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency generator that provides a transaction-scoped AsyncSession."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
