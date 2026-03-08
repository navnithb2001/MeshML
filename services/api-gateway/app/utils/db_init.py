"""Database initialization and migration utilities"""

from sqlalchemy import inspect
import logging

from app.utils.database import engine, Base
from app.models import User, Group, GroupMember, GroupInvitation, Worker, Job

logger = logging.getLogger(__name__)


async def create_tables():
    """Create all database tables"""
    logger.info("Creating database tables...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")


async def drop_tables():
    """Drop all database tables (use with caution!)"""
    logger.warning("Dropping all database tables...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.info("Database tables dropped")


async def check_tables_exist() -> bool:
    """Check if all tables exist"""
    async with engine.connect() as conn:
        def _check(connection):
            inspector = inspect(connection)
            tables = inspector.get_table_names()
            required_tables = [
                "users",
                "groups",
                "group_members",
                "group_invitations",
                "workers",
                "jobs"
            ]
            return all(table in tables for table in required_tables)
        
        return await conn.run_sync(_check)


async def init_database():
    """Initialize database (create tables if they don't exist)"""
    tables_exist = await check_tables_exist()
    
    if not tables_exist:
        logger.info("Tables don't exist. Creating...")
        await create_tables()
    else:
        logger.info("Database tables already exist")
