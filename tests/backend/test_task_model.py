"""Task 모델 순수 단위 테스트 — DB 불필요."""
import uuid
from datetime import datetime, timezone

import pytest

from app.models.task import (
    STATE_TRANSITIONS,
    TERMINAL_STATES,
    Task,
    TaskState,
)


class TestStateTransitions:
    def test_all_states_have_transition_entry_or_are_terminal(self):
        non_terminal = {s for s in TaskState if s not in TERMINAL_STATES}
        # Completed/Cancelled은 출발 상태가 될 수 없음
        for state in non_terminal:
            assert state in STATE_TRANSITIONS, f"{state} has no transition entry"

    def test_terminal_states_have_no_outgoing_transitions(self):
        for state in TERMINAL_STATES:
            assert state not in STATE_TRANSITIONS

    def test_valid_transitions_exist(self):
        cases = [
            (TaskState.SejaFinalReview, TaskState.HongmungwanDraft),
            (TaskState.HongmungwanDraft, TaskState.SaganwonFinalReview),
            (TaskState.InProgress, TaskState.FinalReview),
            (TaskState.FinalReview, TaskState.Completed),
            (TaskState.SeungjeongwonAssigned, TaskState.InProgress),
        ]
        for src, dst in cases:
            assert dst in STATE_TRANSITIONS[src], f"{src} → {dst} should be valid"

    def test_invalid_transitions(self):
        # 역방향 전이는 허용되지 않음
        assert TaskState.SejaFinalReview not in STATE_TRANSITIONS.get(TaskState.HongmungwanDraft, set())
        assert TaskState.InProgress not in STATE_TRANSITIONS.get(TaskState.Completed, set()) or TaskState.Completed in TERMINAL_STATES

    def test_cancellation_allowed_from_most_states(self):
        for state, targets in STATE_TRANSITIONS.items():
            assert TaskState.Cancelled in targets, f"{state} should allow cancellation"

    def test_blocked_can_return_to_multiple_states(self):
        blocked_targets = STATE_TRANSITIONS[TaskState.Blocked]
        assert len(blocked_targets) >= 4


class TestOrgForState:
    def test_seja_state_maps_to_seja_org(self):
        assert Task.org_for_state(TaskState.SejaFinalReview) == "세자"

    def test_hongmungwan_maps_correctly(self):
        assert Task.org_for_state(TaskState.HongmungwanDraft) == "홍문관"

    def test_in_progress_uses_assignee_org(self):
        assert Task.org_for_state(TaskState.InProgress, "호조") == "호조"

    def test_in_progress_without_assignee_defaults(self):
        assert Task.org_for_state(TaskState.InProgress) == "육조"

    def test_ready_uses_assignee_org(self):
        assert Task.org_for_state(TaskState.Ready, "예조") == "예조"

    def test_unknown_state_falls_back_to_assignee_org(self):
        assert Task.org_for_state(TaskState.Completed, "병조") == "병조"


class TestTaskToDict:
    def _make_task(self, **kwargs) -> Task:
        now = datetime.now(timezone.utc)
        defaults = dict(
            task_id=uuid.uuid4(),
            trace_id=str(uuid.uuid4()),
            title="테스트 업무",
            description="설명",
            priority="상",
            state=TaskState.SejaFinalReview,
            org="세자",
            creator="emperor",
            assignee_org="호조",
            tags=["태그1"],
            flow_log=[],
            progress_log=[],
            todos=[],
            scheduler={},
            meta={},
            official="admin",
            now="진행 중",
            eta="-",
            block="없음",
            output="",
            archived=False,
            template_id="",
            template_params={},
            ac="",
            target_dept="호조",
            created_at=now,
            updated_at=now,
        )
        defaults.update(kwargs)
        return Task(**defaults)

    def test_to_dict_contains_required_keys(self):
        t = self._make_task()
        d = t.to_dict()
        for key in ("task_id", "title", "state", "priority", "creator", "tags", "flow_log"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_state_is_string(self):
        t = self._make_task()
        d = t.to_dict()
        assert isinstance(d["state"], str)
        assert d["state"] == "SejaFinalReview"

    def test_to_dict_legacy_compat_fields(self):
        t = self._make_task()
        d = t.to_dict()
        # 기존 프론트엔드 호환 필드 존재 확인
        assert "id" in d
        assert "org" in d
        assert "official" in d
        assert "createdAt" in d
        assert "updatedAt" in d

    def test_to_dict_task_id_is_string(self):
        t = self._make_task()
        d = t.to_dict()
        assert isinstance(d["task_id"], str)

    def test_to_dict_none_meta_defaults_to_empty_dict(self):
        t = self._make_task(meta=None)
        d = t.to_dict()
        assert d["meta"] == {}

    def test_to_dict_none_tags_defaults_to_empty_list(self):
        t = self._make_task(tags=None)
        d = t.to_dict()
        assert d["tags"] == []
