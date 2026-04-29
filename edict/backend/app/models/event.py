"""Event 모델 — 이벤트 영속성 테이블, 재생 및 감사 지원.

각 이벤트는 시스템 동작(업무 생성, 상태 변경, Agent 사고, Todo 업데이트 등)에 대응.
Edict Architecture §3 이벤트 구조 규격 준수.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..db import Base


class Event(Base):
    """이벤트 테이블 — 모든 시스템 이벤트의 영속성 기록."""
    __tablename__ = "events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(32), nullable=False, index=True, comment="연관 업무 ID")
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # 이벤트 분류
    topic = Column(String(128), nullable=False, index=True, comment="이벤트 주제, 예: task.created")
    event_type = Column(String(128), nullable=False, comment="이벤트 유형, 예: state.changed")
    producer = Column(String(128), nullable=False, comment="이벤트 생산자, 예: orchestrator:v1")

    # 이벤트 데이터
    payload = Column(JSONB, default=dict, comment="이벤트 페이로드")
    meta = Column(JSONB, default=dict, comment="메타데이터 {priority, model, version}")

    __table_args__ = (
        Index("ix_events_trace_topic", "trace_id", "topic"),
        Index("ix_events_timestamp", "timestamp"),
    )

    def to_dict(self) -> dict:
        return {
            "event_id": str(self.event_id),
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "topic": self.topic,
            "event_type": self.event_type,
            "producer": self.producer,
            "payload": self.payload or {},
            "meta": self.meta or {},
        }
