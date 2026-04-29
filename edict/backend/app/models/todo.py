"""Todo 모델 — 구조화된 하위 업무.

Edict Architecture §4 Todo JSON Schema 준수.
계층 구조(parent_id) 및 checkpoint 추적 지원.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..db import Base


class Todo(Base):
    """구조화된 하위 업무 테이블."""
    __tablename__ = "todos"

    todo_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(32), nullable=False, index=True, comment="연관 업무 ID")
    parent_id = Column(UUID(as_uuid=True), nullable=True, comment="상위 todo_id (트리 구조)")

    title = Column(String(256), nullable=False, comment="하위 업무 제목")
    description = Column(Text, default="", comment="상세 설명")
    owner = Column(String(64), default="", comment="담당 부서")
    assignee_agent = Column(String(32), default="", comment="실행 Agent")

    status = Column(String(32), nullable=False, default="open", index=True,
                    comment="상태: open|in_progress|done|cancelled")
    priority = Column(String(16), default="normal", comment="우선순위: low|normal|high|urgent")
    estimated_cost = Column(Float, default=0.0, comment="예상 token 소모량")

    created_by = Column(String(64), default="", comment="생성자")
    checkpoints = Column(JSONB, default=list, comment="체크포인트 [{name, status}]")
    metadata_ = Column("metadata", JSONB, default=dict, comment="확장 메타데이터")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_todos_trace_status", "trace_id", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "todo_id": str(self.todo_id),
            "trace_id": self.trace_id,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "title": self.title,
            "description": self.description,
            "owner": self.owner,
            "assignee_agent": self.assignee_agent,
            "status": self.status,
            "priority": self.priority,
            "estimated_cost": self.estimated_cost,
            "created_by": self.created_by,
            "checkpoints": self.checkpoints or [],
            "metadata": self.metadata_ or {},
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }
