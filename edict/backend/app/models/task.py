"""Task 모델 — 조선식 업무 관리 핵심 테이블."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Enum, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..db import Base


class TaskState(str, enum.Enum):
    """업무 상태 열거형 — 조선식 업무 흐름 매핑."""

    SejaFinalReview = "SejaFinalReview"
    HongmungwanDraft = "HongmungwanDraft"
    SaganwonFinalReview = "SaganwonFinalReview"
    SeungjeongwonAssigned = "SeungjeongwonAssigned"
    Ready = "Ready"
    InProgress = "InProgress"
    FinalReview = "FinalReview"
    Completed = "Completed"
    Blocked = "Blocked"
    Cancelled = "Cancelled"
    Pending = "Pending"
    PendingConfirm = "PendingConfirm"


TERMINAL_STATES = {TaskState.Completed, TaskState.Cancelled}

STATE_TRANSITIONS = {
    TaskState.Pending: {TaskState.SejaFinalReview, TaskState.Cancelled},
    TaskState.SejaFinalReview: {TaskState.HongmungwanDraft, TaskState.Cancelled},
    TaskState.HongmungwanDraft: {TaskState.SaganwonFinalReview, TaskState.Cancelled, TaskState.Blocked},
    TaskState.SaganwonFinalReview: {TaskState.SeungjeongwonAssigned, TaskState.HongmungwanDraft, TaskState.Cancelled},
    TaskState.SeungjeongwonAssigned: {TaskState.InProgress, TaskState.Ready, TaskState.Cancelled, TaskState.Blocked},
    TaskState.Ready: {TaskState.InProgress, TaskState.Cancelled, TaskState.Blocked},
    TaskState.InProgress: {TaskState.FinalReview, TaskState.Completed, TaskState.Blocked, TaskState.Cancelled},
    TaskState.FinalReview: {TaskState.Completed, TaskState.SaganwonFinalReview, TaskState.InProgress, TaskState.Cancelled, TaskState.PendingConfirm},
    TaskState.PendingConfirm: {TaskState.Completed, TaskState.FinalReview, TaskState.Cancelled},
    TaskState.Blocked: {
        TaskState.SejaFinalReview,
        TaskState.HongmungwanDraft,
        TaskState.SaganwonFinalReview,
        TaskState.SeungjeongwonAssigned,
        TaskState.Ready,
        TaskState.InProgress,
        TaskState.FinalReview,
        TaskState.Cancelled,
    },
}

STATE_AGENT_MAP = {
    TaskState.SejaFinalReview: "seja",
    TaskState.HongmungwanDraft: "hongmungwan",
    TaskState.SaganwonFinalReview: "saganwon",
    TaskState.SeungjeongwonAssigned: "seungjeongwon",
    TaskState.FinalReview: "seungjeongwon",
    TaskState.PendingConfirm: "seungjeongwon",
    TaskState.Pending: "hongmungwan",
}

ORG_AGENT_MAP = {
    "호조": "hojo",
    "예조": "yejo",
    "병조": "byeongjo",
    "형조": "hyeongjo",
    "공조": "gongjo",
    "이조": "ijo",
}

STATE_ORG_MAP = {
    TaskState.SejaFinalReview: "세자",
    TaskState.HongmungwanDraft: "홍문관",
    TaskState.SaganwonFinalReview: "사간원",
    TaskState.SeungjeongwonAssigned: "승정원",
    TaskState.FinalReview: "승정원",
    TaskState.PendingConfirm: "승정원",
    TaskState.Pending: "홍문관",
}


class Task(Base):
    """조선식 업무 관리 테이블."""

    __tablename__ = "tasks"

    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(64), nullable=False, default=lambda: str(uuid.uuid4()), comment="추적 링크 ID")
    title = Column(String(200), nullable=False, comment="업무 제목")
    description = Column(Text, default="", comment="업무 설명")
    priority = Column(String(10), default="중", comment="우선순위")
    state = Column(
        Enum(TaskState, name="task_state", native_enum=False, validate_strings=True),
        nullable=False,
        default=TaskState.SejaFinalReview,
        comment="업무 상태",
    )
    assignee_org = Column(String(50), nullable=True, comment="목표 실행 부서")
    creator = Column(String(50), default="emperor", comment="생성자")
    tags = Column(JSONB, default=list, comment="태그")
    meta = Column(JSONB, default=dict, comment="확장 메타데이터")

    # 기존 칸반 필드와의 호환성 유지
    org = Column(String(32), nullable=False, default="세자", comment="현재 실행 부서")
    official = Column(String(32), default="", comment="책임 관리")
    now = Column(Text, default="", comment="현재 진행 상황 설명")
    eta = Column(String(64), default="-", comment="예상 완료 시간")
    block = Column(Text, default="없음", comment="차단 사유")
    output = Column(Text, default="", comment="최종 산출물")
    archived = Column(Boolean, default=False, comment="보관 여부")

    flow_log = Column(JSONB, default=list, comment="流转日志 [{at, from, to, remark}]")
    progress_log = Column(JSONB, default=list, comment="进展日志 [{at, agent, text, todos}]")
    todos = Column(JSONB, default=list, comment="子작업 [{id, title, status, detail}]")
    scheduler = Column(JSONB, default=dict, comment="调度器元数据")
    template_id = Column(String(64), default="", comment="模板ID")
    template_params = Column(JSONB, default=dict, comment="模板参数")
    ac = Column(Text, default="", comment="验收标准")
    target_dept = Column(String(64), default="", comment="目标部门")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_tasks_trace_id", "trace_id"),
        Index("ix_tasks_assignee_org", "assignee_org"),
        Index("ix_tasks_created_at", "created_at"),
        Index("ix_tasks_state", "state"),
        Index("ix_tasks_state_archived", "state", "archived"),
        Index("ix_tasks_updated_at", "updated_at"),
    )

    @staticmethod
    def org_for_state(state: TaskState, assignee_org: str | None = None) -> str:
        if state in {TaskState.InProgress, TaskState.Ready}:
            return assignee_org or "육조"
        return STATE_ORG_MAP.get(state, assignee_org or "세자")

    def to_dict(self) -> dict[str, Any]:
        """API 응답 형식으로 직렬화, 기존 live_status 필드와 호환."""

        state_value = self.state.value if isinstance(self.state, TaskState) else str(self.state or "")
        meta = self.meta or {}
        scheduler = self.scheduler or {}
        task_id = str(self.task_id) if self.task_id else ""
        updated_at = self.updated_at.isoformat() if self.updated_at else ""
        legacy_output = self.output or meta.get("output") or meta.get("legacy_output", "")

        return {
            "task_id": task_id,
            "trace_id": self.trace_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "state": state_value,
            "assignee_org": self.assignee_org,
            "creator": self.creator,
            "tags": self.tags or [],
            "meta": meta,
            "flow_log": self.flow_log or [],
            "progress_log": self.progress_log or [],
            "todos": self.todos or [],
            "scheduler": scheduler,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": updated_at,
            # 기존 프론트엔드 호환 필드
            "id": task_id,
            "org": self.org or self.org_for_state(self.state, self.assignee_org),
            "official": self.official or self.creator,
            "now": self.now or self.description,
            "eta": self.eta if self.eta != "-" else updated_at,
            "block": self.block,
            "output": legacy_output,
            "archived": self.archived,
            "templateId": self.template_id,
            "templateParams": self.template_params or {},
            "ac": self.ac,
            "targetDept": self.target_dept,
            "_scheduler": scheduler,
            "createdAt": self.created_at.isoformat() if self.created_at else "",
            "updatedAt": updated_at,
        }
