"""Tasks API 테스트 — FastAPI TestClient + dependency override."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.models.task import Task, TaskState
from app.services.task_service import TaskService


def _make_mock_task(title="테스트", state=TaskState.SejaFinalReview, **kwargs):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    t = MagicMock(spec=Task)
    t.task_id = uuid.uuid4()
    t.trace_id = str(uuid.uuid4())
    t.title = title
    t.state = state
    t.description = ""
    t.priority = "중"
    t.assignee_org = None
    t.creator = "emperor"
    t.tags = []
    t.flow_log = []
    t.progress_log = []
    t.todos = []
    t.scheduler = {}
    t.meta = {}
    t.org = "세자"
    t.official = "emperor"
    t.now = ""
    t.eta = "-"
    t.block = "없음"
    t.output = ""
    t.archived = False
    t.template_id = ""
    t.template_params = {}
    t.ac = ""
    t.target_dept = ""
    t.created_at = now
    t.updated_at = now
    for k, v in kwargs.items():
        setattr(t, k, v)
    t.to_dict.return_value = {
        "task_id": str(t.task_id),
        "trace_id": t.trace_id,
        "title": title,
        "state": state.value,
        "priority": "중",
        "description": "",
        "assignee_org": None,
        "creator": "emperor",
        "tags": [],
        "flow_log": [],
        "progress_log": [],
        "todos": [],
        "scheduler": {},
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    return t


@pytest.fixture
def mock_svc():
    svc = AsyncMock(spec=TaskService)
    return svc


@pytest.fixture
def app_with_override(mock_svc):
    from app.main import app
    from app.api.tasks import get_task_service
    app.dependency_overrides[get_task_service] = lambda: mock_svc
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app_with_override):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_override), base_url="http://test"
    ) as c:
        yield c


class TestHealthEndpoint:
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestListTasks:
    async def test_list_returns_empty(self, client, mock_svc):
        mock_svc.list_tasks.return_value = []
        resp = await client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tasks"] == []
        assert data["count"] == 0

    async def test_list_returns_tasks(self, client, mock_svc):
        task = _make_mock_task("업무A")
        mock_svc.list_tasks.return_value = [task]
        resp = await client.get("/api/tasks")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    async def test_list_passes_state_filter(self, client, mock_svc):
        mock_svc.list_tasks.return_value = []
        await client.get("/api/tasks?state=InProgress")
        mock_svc.list_tasks.assert_called_once()
        call_kwargs = mock_svc.list_tasks.call_args.kwargs
        assert call_kwargs["state"] == TaskState.InProgress


class TestCreateTask:
    async def test_create_returns_201(self, client, mock_svc):
        task = _make_mock_task("새업무")
        mock_svc.create_task.return_value = task
        resp = await client.post("/api/tasks", json={"title": "새업무"})
        assert resp.status_code == 201

    async def test_create_returns_task_id(self, client, mock_svc):
        task = _make_mock_task("업무B")
        mock_svc.create_task.return_value = task
        resp = await client.post("/api/tasks", json={"title": "업무B"})
        data = resp.json()
        assert "task_id" in data
        assert "state" in data

    async def test_create_passes_fields(self, client, mock_svc):
        task = _make_mock_task()
        mock_svc.create_task.return_value = task
        await client.post("/api/tasks", json={
            "title": "업무C",
            "priority": "상",
            "assignee_org": "호조",
            "tags": ["긴급"],
        })
        mock_svc.create_task.assert_called_once()
        kwargs = mock_svc.create_task.call_args.kwargs
        assert kwargs["title"] == "업무C"
        assert kwargs["priority"] == "상"
        assert kwargs["assignee_org"] == "호조"


class TestGetTask:
    async def test_get_existing_task(self, client, mock_svc):
        task = _make_mock_task("조회업무")
        mock_svc.get_task.return_value = task
        resp = await client.get(f"/api/tasks/{task.task_id}")
        assert resp.status_code == 200

    async def test_get_nonexistent_returns_404(self, client, mock_svc):
        mock_svc.get_task.side_effect = ValueError("not found")
        resp = await client.get(f"/api/tasks/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestTransitionTask:
    async def test_transition_success(self, client, mock_svc):
        task = _make_mock_task(state=TaskState.HongmungwanDraft)
        mock_svc.transition_state.return_value = task
        resp = await client.post(
            f"/api/tasks/{uuid.uuid4()}/transition",
            json={"new_state": "HongmungwanDraft", "agent": "seja", "reason": "초안 요청"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "HongmungwanDraft"

    async def test_transition_invalid_state_returns_400(self, client, mock_svc):
        resp = await client.post(
            f"/api/tasks/{uuid.uuid4()}/transition",
            json={"new_state": "InvalidState"},
        )
        assert resp.status_code == 400

    async def test_transition_invalid_logic_returns_400(self, client, mock_svc):
        mock_svc.transition_state.side_effect = ValueError("Invalid transition")
        resp = await client.post(
            f"/api/tasks/{uuid.uuid4()}/transition",
            json={"new_state": "Completed"},
        )
        assert resp.status_code == 400


class TestTaskStats:
    async def test_stats_endpoint(self, client, mock_svc):
        mock_svc.count_tasks.return_value = 0
        resp = await client.get("/api/tasks/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_state" in data


class TestAgentsApi:
    async def test_list_agents(self, client):
        resp = await client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert len(data["agents"]) > 0

    async def test_agent_has_required_fields(self, client):
        resp = await client.get("/api/agents")
        agent = resp.json()["agents"][0]
        for field in ("id", "name", "role"):
            assert field in agent
