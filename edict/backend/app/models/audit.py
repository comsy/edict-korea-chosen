"""AuditLog 모델 — 독립 감사 로그 테이블.

모든 Agent 및 시스템의 업무 조작 기록, "누가 언제 어떤 업무에 대해 무엇을 했는지" 조회 지원.
flow_log (JSONB 필드)와 달리, 감사 로그는 독립 테이블로 업무 간 검색 가능.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..db import Base


class AuditLog(Base):
    """감사 로그 테이블."""

    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    task_id = Column(String(64), nullable=True, comment="연관 업무 ID")
    trace_id = Column(String(64), nullable=True, comment="추적 링크 ID")
    agent_id = Column(String(50), nullable=True, comment="조작을 실행한 Agent")
    action = Column(String(50), nullable=False, comment="조작 유형: state/flow/todo/confirm/memory/permission_denied")
    old_value = Column(JSONB, nullable=True, comment="변경 전 상태")
    new_value = Column(JSONB, nullable=True, comment="변경 후 상태")
    reason = Column(Text, default="", comment="조작 사유/비고")
    meta = Column(JSONB, default=dict, comment="확장 메타데이터 (tokens, cost, duration)")

    __table_args__ = (
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_task_id", "task_id"),
        Index("ix_audit_agent_id", "agent_id"),
        Index("ix_audit_action", "action"),
    )
