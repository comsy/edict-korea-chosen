"""업무 서비스 레이어 — CRUD + 상태기 로직.

모든 업무 규칙을 여기에 집중:
- 업무 생성 → outbox 테이블에 이벤트 기록 (같은 트랜잭션)
- 상태 전이 → 합법성 검증 + SELECT FOR UPDATE 동시 쓰기 방지 + outbox 이벤트
- 조회, 필터, 집계

이벤트 전달은 OutboxRelay worker가 비동기 수행, DB/Event 원자적 일관성 보장.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.outbox import OutboxEvent
from ..models.task import Task, TaskState, STATE_TRANSITIONS, TERMINAL_STATES
from .event_bus import (
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_DISPATCH,
)

log = logging.getLogger("edict.task_service")


class TaskService:
    def __init__(self, db: AsyncSession, event_bus=None):
        self.db = db
        # event_bus는 request_dispatch 등 직접 발행 시 사용
        self.bus = event_bus

    # ── 생성 ──

    async def create_task(
        self,
        title: str,
        description: str = "",
        priority: str = "중",
        assignee_org: str | None = None,
        creator: str = "emperor",
        tags: list[str] | None = None,
        initial_state: TaskState = TaskState.SejaFinalReview,
        meta: dict | None = None,
    ) -> Task:
        """업무 생성 — outbox 테이블에 이벤트 기록 (같은 트랜잭션 원자 커밋)."""
        now = datetime.now(timezone.utc)
        trace_id = str(uuid.uuid4())
        target_org = Task.org_for_state(initial_state, assignee_org)
        task_meta = meta or {}

        task = Task(
            trace_id=trace_id,
            title=title,
            description=description,
            priority=priority,
            state=initial_state,
            assignee_org=assignee_org,
            creator=creator,
            tags=tags or [],
            org=target_org,
            official=creator,
            now=description or "업무 생성",
            target_dept=assignee_org or "",
            flow_log=[
                {
                    "from": None,
                    "to": initial_state.value,
                    "agent": "system",
                    "reason": "업무 생성",
                    "ts": now.isoformat(),
                }
            ],
            progress_log=[],
            todos=[],
            scheduler={},
            meta=task_meta,
        )
        self.db.add(task)
        await self.db.flush()

        # 事件写入 outbox — 与 task 同一事务，原子提交
        outbox = OutboxEvent(
            topic=TOPIC_TASK_CREATED,
            trace_id=trace_id,
            event_type="task.created",
            producer="task_service",
            payload={
                "task_id": str(task.task_id),
                "title": title,
                "state": initial_state.value,
                "priority": priority,
                "assignee_org": assignee_org,
            },
        )
        self.db.add(outbox)

        await self.db.commit()
        log.info(f"Created task {task.task_id}: {title} [{initial_state.value}]")
        return task

    # ── 상태 전이 ──

    async def transition_state(
        self,
        task_id: uuid.UUID,
        new_state: TaskState,
        agent: str = "system",
        reason: str = "",
    ) -> Task:
        """상태 전이 실행. SELECT FOR UPDATE로 동시 flow_log 손실 방지."""
        # 행 레벨 배타 잠금 — 같은 업무의 동시 쓰기 직렬화
        stmt = select(Task).where(Task.task_id == task_id).with_for_update()
        result = await self.db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        old_state = task.state

        # 합법 전이 검증
        allowed = STATE_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {old_state.value} → {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        task.state = new_state
        task.org = Task.org_for_state(new_state, task.assignee_org)
        if reason:
            task.now = reason
        task.updated_at = datetime.now(timezone.utc)

        # 행 잠금 보호 하에 flow_log 안전 추가
        flow_entry = {
            "from": old_state.value,
            "to": new_state.value,
            "agent": agent,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if task.flow_log is None:
            task.flow_log = []
        task.flow_log = [*task.flow_log, flow_entry]

        # outbox에 이벤트 기록 (같은 트랜잭션)
        topic = TOPIC_TASK_COMPLETED if new_state in TERMINAL_STATES else TOPIC_TASK_STATUS
        outbox = OutboxEvent(
            topic=topic,
            trace_id=str(task.trace_id),
            event_type=f"task.state.{new_state.value}",
            producer=agent,
            payload={
                "task_id": str(task_id),
                "from": old_state.value,
                "to": new_state.value,
                "reason": reason,
                "assignee_org": task.assignee_org,
            },
        )
        self.db.add(outbox)

        await self.db.commit()
        log.info(f"Task {task_id} state: {old_state.value} → {new_state.value} by {agent}")
        return task

    # ── 배분 요청 ──

    async def request_dispatch(
        self,
        task_id: uuid.UUID,
        target_agent: str,
        message: str = "",
    ):
        """task.dispatch 이벤트를 outbox에 발행, OutboxRelay 전달 후 DispatchWorker가 소비."""
        task = await self._get_task(task_id)
        outbox = OutboxEvent(
            topic=TOPIC_TASK_DISPATCH,
            trace_id=str(task.trace_id),
            event_type="task.dispatch.request",
            producer="task_service",
            payload={
                "task_id": str(task_id),
                "agent": target_agent,
                "message": message,
                "state": task.state.value,
            },
        )
        self.db.add(outbox)
        await self.db.commit()
        log.info(f"Dispatch requested: task {task_id} → agent {target_agent}")

    # ── 진행 상황/비고 갱신 ──

    async def add_progress(
        self,
        task_id: uuid.UUID,
        agent: str,
        content: str,
    ) -> Task:
        task = await self._get_task(task_id)
        entry = {
            "agent": agent,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if task.progress_log is None:
            task.progress_log = []
        task.progress_log = [*task.progress_log, entry]
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return task

    async def update_todos(
        self,
        task_id: uuid.UUID,
        todos: list[dict],
    ) -> Task:
        task = await self._get_task(task_id)
        task.todos = todos
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return task

    async def update_scheduler(
        self,
        task_id: uuid.UUID,
        scheduler: dict,
    ) -> Task:
        task = await self._get_task(task_id)
        task.scheduler = scheduler
        task.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return task

    # ── 조회 ──

    async def get_task(self, task_id: uuid.UUID) -> Task:
        return await self._get_task(task_id)

    async def list_tasks(
        self,
        state: TaskState | None = None,
        assignee_org: str | None = None,
        priority: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        stmt = select(Task)
        conditions = []
        if state is not None:
            conditions.append(Task.state == state)
        if assignee_org is not None:
            conditions.append(Task.assignee_org == assignee_org)
        if priority is not None:
            conditions.append(Task.priority == priority)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_live_status(self) -> dict[str, Any]:
        """live_status.json 형식 호환 전역 상태 생성."""
        tasks = await self.list_tasks(limit=200)
        active_tasks = {}
        completed_tasks = {}
        for t in tasks:
            d = t.to_dict()
            if t.state in TERMINAL_STATES:
                completed_tasks[str(t.task_id)] = d
            else:
                active_tasks[str(t.task_id)] = d
        return {
            "tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def count_tasks(self, state: TaskState | None = None) -> int:
        stmt = select(func.count(Task.task_id))
        if state is not None:
            stmt = stmt.where(Task.state == state)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    # ── 내부 ──

    async def _get_task(self, task_id: uuid.UUID) -> Task:
        task = await self.db.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        return task
