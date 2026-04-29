"""TaskService 통합 테스트 — SQLite 인메모리 DB 사용."""
import uuid

import pytest

from app.models.outbox import OutboxEvent
from app.models.task import TaskState, TERMINAL_STATES
from app.services.task_service import TaskService
from sqlalchemy import select


class TestCreateTask:
    async def test_returns_task_with_correct_title(self, task_service):
        task = await task_service.create_task(title="업무A", priority="상")
        assert task.title == "업무A"
        assert task.priority == "상"

    async def test_default_state_is_seja_final_review(self, task_service):
        task = await task_service.create_task(title="업무B")
        assert task.state == TaskState.SejaFinalReview

    async def test_assigns_trace_id(self, task_service):
        task = await task_service.create_task(title="업무C")
        assert task.trace_id is not None

    async def test_flow_log_contains_creation_entry(self, task_service):
        task = await task_service.create_task(title="업무D")
        assert len(task.flow_log) == 1
        assert task.flow_log[0]["from"] is None
        assert task.flow_log[0]["to"] == TaskState.SejaFinalReview.value

    async def test_creates_outbox_event(self, task_service, db_session):
        await task_service.create_task(title="업무E")
        result = await db_session.execute(select(OutboxEvent))
        events = result.scalars().all()
        assert len(events) == 1
        assert events[0].event_type == "task.created"

    async def test_custom_initial_state(self, task_service):
        task = await task_service.create_task(
            title="업무F",
            initial_state=TaskState.InProgress,
            assignee_org="호조",
        )
        assert task.state == TaskState.InProgress
        assert task.org == "호조"


class TestTransitionState:
    async def test_valid_transition_updates_state(self, task_service):
        task = await task_service.create_task(title="전이테스트")
        task = await task_service.transition_state(
            task.task_id,
            TaskState.HongmungwanDraft,
            agent="seja",
            reason="초안 작성 요청",
        )
        assert task.state == TaskState.HongmungwanDraft

    async def test_flow_log_grows_on_transition(self, task_service):
        task = await task_service.create_task(title="로그테스트")
        task = await task_service.transition_state(task.task_id, TaskState.HongmungwanDraft)
        assert len(task.flow_log) == 2
        assert task.flow_log[1]["from"] == TaskState.SejaFinalReview.value
        assert task.flow_log[1]["to"] == TaskState.HongmungwanDraft.value

    async def test_invalid_transition_raises_value_error(self, task_service):
        task = await task_service.create_task(title="오류테스트")
        with pytest.raises(ValueError, match="Invalid transition"):
            await task_service.transition_state(task.task_id, TaskState.Completed)

    async def test_not_found_raises_value_error(self, task_service):
        with pytest.raises(ValueError, match="not found"):
            await task_service.transition_state(uuid.uuid4(), TaskState.HongmungwanDraft)

    async def test_terminal_state_writes_completed_topic(self, task_service, db_session):
        # InProgress → Completed 경로
        task = await task_service.create_task(title="완료테스트", initial_state=TaskState.InProgress)
        await task_service.transition_state(task.task_id, TaskState.Completed)
        result = await db_session.execute(
            select(OutboxEvent).where(OutboxEvent.event_type == f"task.state.{TaskState.Completed.value}")
        )
        ev = result.scalar_one_or_none()
        assert ev is not None
        assert ev.topic == "task.completed"

    async def test_non_terminal_transition_writes_status_topic(self, task_service, db_session):
        task = await task_service.create_task(title="상태변경테스트")
        await task_service.transition_state(task.task_id, TaskState.HongmungwanDraft)
        result = await db_session.execute(
            select(OutboxEvent).where(OutboxEvent.topic == "task.status")
        )
        ev = result.scalar_one_or_none()
        assert ev is not None

    async def test_reason_updates_task_now_field(self, task_service):
        task = await task_service.create_task(title="이유테스트")
        task = await task_service.transition_state(
            task.task_id, TaskState.HongmungwanDraft, reason="초안 필요"
        )
        assert task.now == "초안 필요"


class TestProgressAndTodos:
    async def test_add_progress_appends_entry(self, task_service):
        task = await task_service.create_task(title="진행테스트")
        task = await task_service.add_progress(task.task_id, agent="hojo", content="50% 완료")
        assert len(task.progress_log) == 1
        assert task.progress_log[0]["agent"] == "hojo"
        assert task.progress_log[0]["content"] == "50% 완료"

    async def test_add_progress_multiple_entries(self, task_service):
        task = await task_service.create_task(title="다중진행")
        await task_service.add_progress(task.task_id, "a1", "1단계")
        task = await task_service.add_progress(task.task_id, "a2", "2단계")
        assert len(task.progress_log) == 2

    async def test_update_todos_replaces_list(self, task_service):
        task = await task_service.create_task(title="TODO테스트")
        todos = [{"id": "1", "title": "항목1", "status": "pending"}]
        task = await task_service.update_todos(task.task_id, todos)
        assert len(task.todos) == 1
        assert task.todos[0]["title"] == "항목1"

    async def test_update_scheduler_saves_dict(self, task_service):
        task = await task_service.create_task(title="스케줄러테스트")
        sched = {"next_run": "2026-05-01T00:00:00Z", "interval": 3600}
        task = await task_service.update_scheduler(task.task_id, sched)
        assert task.scheduler["interval"] == 3600


class TestListAndCount:
    async def test_list_tasks_returns_all(self, task_service):
        await task_service.create_task(title="목록1")
        await task_service.create_task(title="목록2")
        tasks = await task_service.list_tasks()
        assert len(tasks) == 2

    async def test_list_tasks_filter_by_state(self, task_service):
        await task_service.create_task(title="필터1")
        await task_service.create_task(title="필터2", initial_state=TaskState.InProgress)
        tasks = await task_service.list_tasks(state=TaskState.InProgress)
        assert len(tasks) == 1
        assert tasks[0].title == "필터2"

    async def test_list_tasks_filter_by_assignee_org(self, task_service):
        await task_service.create_task(title="호조업무", assignee_org="호조")
        await task_service.create_task(title="예조업무", assignee_org="예조")
        tasks = await task_service.list_tasks(assignee_org="호조")
        assert len(tasks) == 1
        assert tasks[0].assignee_org == "호조"

    async def test_count_tasks_total(self, task_service):
        await task_service.create_task(title="카운트1")
        await task_service.create_task(title="카운트2")
        assert await task_service.count_tasks() == 2

    async def test_count_tasks_by_state(self, task_service):
        await task_service.create_task(title="진행중1", initial_state=TaskState.InProgress)
        await task_service.create_task(title="대기중1")
        assert await task_service.count_tasks(TaskState.InProgress) == 1
        assert await task_service.count_tasks(TaskState.SejaFinalReview) == 1

    async def test_list_tasks_limit(self, task_service):
        for i in range(5):
            await task_service.create_task(title=f"업무{i}")
        tasks = await task_service.list_tasks(limit=3)
        assert len(tasks) == 3

    async def test_get_task_returns_task(self, task_service):
        created = await task_service.create_task(title="조회테스트")
        fetched = await task_service.get_task(created.task_id)
        assert fetched.task_id == created.task_id

    async def test_get_task_not_found_raises(self, task_service):
        with pytest.raises(ValueError, match="not found"):
            await task_service.get_task(uuid.uuid4())

    async def test_get_live_status_structure(self, task_service):
        await task_service.create_task(title="활성업무")
        await task_service.create_task(title="완료업무", initial_state=TaskState.Completed)
        status = await task_service.get_live_status()
        assert "tasks" in status
        assert "completed_tasks" in status
        assert "last_updated" in status
        assert len(status["completed_tasks"]) == 1
