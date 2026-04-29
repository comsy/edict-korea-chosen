"""Events API — 이벤트조회与审计。"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from ..db import get_db
from ..models.event import Event
from ..services.event_bus import get_event_bus

log = logging.getLogger("edict.api.events")
router = APIRouter()


@router.get("")
async def list_events(
    trace_id: str | None = None,
    topic: str | None = None,
    producer: str | None = None,
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
):
    """조회持久化이벤트（从 Postgres event 表）。"""
    stmt = select(Event)
    if trace_id:
        stmt = stmt.where(Event.trace_id == trace_id)
    if topic:
        stmt = stmt.where(Event.topic == topic)
    if producer:
        stmt = stmt.where(Event.producer == producer)
    stmt = stmt.order_by(Event.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()
    return {
        "events": [
            {
                "event_id": str(e.event_id),
                "trace_id": e.trace_id,
                "topic": e.topic,
                "event_type": e.event_type,
                "producer": e.producer,
                "payload": e.payload,
                "meta": e.meta,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in events
        ],
        "count": len(events),
    }


@router.get("/stream-info")
async def stream_info(topic: str = Query(description="Stream topic")):
    """조회 Redis Stream 实时정보。"""
    bus = await get_event_bus()
    info = await bus.stream_info(topic)
    return {"topic": topic, "info": info}


@router.get("/topics")
async def list_topics():
    """列出所有可用이벤트 topic。"""
    from ..services.event_bus import (
        TOPIC_TASK_CREATED,
        TOPIC_TASK_STATUS,
        TOPIC_TASK_DISPATCH,
        TOPIC_TASK_COMPLETED,
        TOPIC_TASK_STALLED,
        TOPIC_AGENT_THOUGHTS,
        TOPIC_AGENT_HEARTBEAT,
    )
    return {
        "topics": [
            {"name": TOPIC_TASK_CREATED, "description": "작업 생성"},
            {"name": TOPIC_TASK_STATUS, "description": "상태 변경"},
            {"name": TOPIC_TASK_DISPATCH, "description": "Agent 발송"},
            {"name": TOPIC_TASK_COMPLETED, "description": "작업 완료"},
            {"name": TOPIC_TASK_STALLED, "description": "작업 정체"},
            {"name": TOPIC_AGENT_THOUGHTS, "description": "Agent 사고 흐름"},
            {"name": TOPIC_AGENT_HEARTBEAT, "description": "Agent 하트비트"},
        ]
    }
