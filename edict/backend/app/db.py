"""SQLAlchemy 비동기 엔진 및 세션 관리."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

_db_url = settings.database_url
_pool_kwargs = (
    {}
    if _db_url.startswith("sqlite")
    else {"pool_size": 10, "max_overflow": 20}
)

engine = create_async_engine(
    _db_url,
    echo=settings.debug,
    pool_pre_ping=not _db_url.startswith("sqlite"),
    **_pool_kwargs,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入 — 获取异步数据库 session。

    提交策略：由服务层显式 commit/flush 控制，
    此处仅负责异常时 rollback，避免双重提交。
    """
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """开发用 — 创建所有表（生产用 Alembic）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
