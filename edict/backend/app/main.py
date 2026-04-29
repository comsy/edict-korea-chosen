"""Edict 백엔드 — FastAPI 애플리케이션 진입점.

Lifespan 관리:
- startup: Redis Event Bus 연결, 데이터베이스 초기화
- shutdown: 연결 종료

라우트:
- /api/tasks — 작업 CRUD
- /api/agents — Agent 정보
- /api/events — 이벤트 조회
- /api/admin — 관리 작업
- /ws — WebSocket 실시간 푸시
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .services.event_bus import get_event_bus
from .api import tasks, agents, events, admin, websocket
from .api import legacy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("edict")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리."""
    settings = get_settings()
    log.info(f"🏛️ Edict Backend starting on port {settings.port}...")

    # Event Bus 연결
    bus = await get_event_bus()
    log.info("✅ Event Bus connected")

    yield

    # 정리
    await bus.close()
    log.info("Edict Backend shutdown complete")


app = FastAPI(
    title="Edict 3사6조",
    description="이벤트 기반 AI Agent 협업 플랫폼",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — 개발 환경에서 모든 출처 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(websocket.router, tags=["websocket"])
app.include_router(legacy.router, prefix="/api/tasks", tags=["legacy"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "engine": "edict"}


@app.get("/api")
async def api_root():
    return {
        "name": "Edict 3사6조 API",
        "version": "2.0.0",
        "endpoints": {
            "tasks": "/api/tasks",
            "agents": "/api/agents",
            "events": "/api/events",
            "admin": "/api/admin",
            "websocket": "/ws",
            "health": "/health",
        },
    }
