"""
Database session management for Model Registry
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator

from .config import settings
from .models import Base

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,  # Disable connection pooling for async
    future=True,
    connect_args={"ssl": False}  # Disable SSL for internal cluster communication
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def create_tables():
    """Create all database tables"""
    # Tables are managed by the main database service
    # Skip table creation to avoid foreign key issues
    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
