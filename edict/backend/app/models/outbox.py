"""OutboxEvent 모델 — Transactional Outbox Pattern.

이벤트를 먼저 비즈니스 데이터와 동일한 트랜잭션에 기록하고, OutboxRelay worker가 비동기로 Redis Streams에 전달.
DB/Event 이중 쓰기 불일치 문제 해결:
- create_task: flush→publish→commit 중 publish 실패로 인한 작업 낭비 방지
- transition_state: 먼저 publish 후 commit 시 commit 실패로 인한 유령 이벤트 방지
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from ..db import Base


class OutboxEvent(Base):
    """발신함 테이블 — 이벤트를 먼저 DB에 쓰고, 전용 worker가 Redis에 전달."""

    __tablename__ = "outbox_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    event_id = Column(
        String(64),
        default=lambda: str(uuid.uuid4()),
        nullable=False,
        unique=True,
    )
    topic = Column(String(100), nullable=False, comment="대상 Redis Stream topic")
    trace_id = Column(String(64), nullable=False)
    event_type = Column(String(100), nullable=False)
    producer = Column(String(100), nullable=False)
    payload = Column(JSONB, default=dict)
    meta = Column(JSONB, default=dict)
    published = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_outbox_unpublished", "published", "id", postgresql_where="published = false"),
        Index("ix_outbox_created_at", "created_at"),
    )
