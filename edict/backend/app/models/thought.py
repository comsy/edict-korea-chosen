"""Thought 모델 — Agent 사고 흐름 영속성.

Edict Architecture §4 Thought JSON Schema 준수.
스트리밍 부분 사고 및 대시보드 실시간 표시 지원.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID

from ..db import Base


class Thought(Base):
    """Agent 사고 기록."""
    __tablename__ = "thoughts"

    thought_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(32), nullable=False, index=True, comment="연관 업무 ID")
    agent = Column(String(32), nullable=False, index=True, comment="Agent 식별자")
    step = Column(Integer, nullable=False, default=0, comment="사고 단계 순번")
    type = Column(
        String(32),
        nullable=False,
        default="reasoning",
        comment="사고 유형: reasoning|query|action_intent|summary",
    )
    source = Column(String(16), default="llm", comment="출처: llm|tool|human")
    content = Column(Text, nullable=False, default="", comment="사고 내용")
    tokens = Column(Integer, default=0, comment="소비 token 수")
    confidence = Column(Float, default=0.0, comment="신뢰도 0-1")
    sensitive = Column(Boolean, default=False, comment="민감 내용 여부")
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_thoughts_trace_agent", "trace_id", "agent"),
        Index("ix_thoughts_timestamp", "timestamp"),
    )

    def to_dict(self) -> dict:
        return {
            "thought_id": str(self.thought_id),
            "trace_id": self.trace_id,
            "agent": self.agent,
            "step": self.step,
            "type": self.type,
            "source": self.source,
            "content": self.content,
            "tokens": self.tokens,
            "confidence": self.confidence,
            "sensitive": self.sensitive,
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
        }
