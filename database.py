# backend/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.config import settings

def _make_async_url(url: str) -> str:
    return url.replace("postgresql://", "postgresql+asyncpg://", 1).split("?")[0] + "?ssl=require"

engine = create_async_engine(_make_async_url(settings.db_url), pool_size=5, max_overflow=10)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def get_session():
    async with SessionLocal() as session:
        yield session
