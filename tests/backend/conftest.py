"""edict/backend 테스트 픽스처."""
import os
import sys
import pathlib

# DB URL을 SQLite 인메모리로 설정 — app.db import 전에 반드시 먼저 실행
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

BACKEND = pathlib.Path(__file__).resolve().parent.parent.parent / "edict" / "backend"
sys.path.insert(0, str(BACKEND))

# lru_cache 초기화 (이미 캐시됐을 경우를 대비)
from app.config import get_settings
get_settings.cache_clear()

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

# SQLite는 JSONB를 모르므로 JSON으로 fallback 처리
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON as _JSON

def _visit_JSONB(self, type_, **kw):
    return self.visit_JSON(_JSON(), **kw)

SQLiteTypeCompiler.visit_JSONB = _visit_JSONB

# SQLite에서 BigInteger PRIMARY KEY는 BIGINT로 처리되어 autoincrement가 안 됨
# INTEGER로 fallback해야 ROWID alias로 자동 증가됨
SQLiteTypeCompiler.visit_big_integer = lambda self, type_, **kw: "INTEGER"


@pytest_asyncio.fixture
async def db_session():
    from app.db import Base
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def task_service(db_session):
    from app.services.task_service import TaskService
    return TaskService(db=db_session)


@pytest_asyncio.fixture
async def event_bus():
    from app.services.event_bus import EventBus
    from fakeredis import aioredis as fake_aioredis
    bus = EventBus()
    bus._redis = fake_aioredis.FakeRedis(decode_responses=True)
    yield bus
    await bus.close()
