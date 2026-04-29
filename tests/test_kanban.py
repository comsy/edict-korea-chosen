"""tests for scripts/kanban_update.py"""
import json
import pathlib
import subprocess
import sys

# Ensure scripts/ is importable
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kanban_update as kb


def test_create_and_get(tmp_path):
    """kanban create + get round-trip."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text("[]", encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_create("TEST-001", "업무 생성 및 조회 기능 검증 테스트", "SejaFinalReview", "공조", "공조판서")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        assert any(t.get("id") == "TEST-001" for t in tasks)
        task = next(t for t in tasks if t["id"] == "TEST-001")
        assert task["title"] == "업무 생성 및 조회 기능 검증 테스트"
        assert task["state"] == "SejaFinalReview"
        assert task["org"] == "세자"
    finally:
        kb.TASKS_FILE = original


def test_move_state(tmp_path):
    """kanban move changes task state."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text(json.dumps([
        {"id": "T-1", "title": "test", "state": "SejaFinalReview"}
    ], ensure_ascii=False), encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_state("T-1", "HongmungwanDraft")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        assert tasks[0]["state"] == "HongmungwanDraft"
    finally:
        kb.TASKS_FILE = original


def test_block_and_unblock(tmp_path):
    """kanban block round-trip."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text(json.dumps([
        {"id": "T-2", "title": "blocker test", "state": "InProgress"}
    ], ensure_ascii=False), encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_block("T-2", "의존성 대기")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        assert tasks[0]["state"] == "Blocked"
        assert tasks[0]["block"] == "의존성 대기"
    finally:
        kb.TASKS_FILE = original


def test_flow_log(tmp_path):
    """cmd_flow appends a flow_log entry."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text(json.dumps([
        {"id": "T-3", "title": "flow test", "state": "HongmungwanDraft", "flow_log": []}
    ], ensure_ascii=False), encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_flow("T-3", "홍문관", "사간원", "기안안을 사간원 심의로 제출")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        task = tasks[0]
        assert len(task["flow_log"]) == 1
        assert task["flow_log"][0]["from"] == "홍문관"
        assert task["flow_log"][0]["to"] == "사간원"
    finally:
        kb.TASKS_FILE = original


def test_done_routes_to_review(tmp_path):
    """cmd_done should route execution output back to FinalReview instead of direct Completed."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text(json.dumps([
        {
            "id": "T-4",
            "title": "done test",
            "state": "InProgress",
            "org": "병조",
            "flow_log": [],
            "todos": [{"id": "1", "title": "마무리", "status": "completed"}],
        }
    ], ensure_ascii=False), encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_done("T-4", "/tmp/output.md", "기능 구현 완료")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        task = tasks[0]
        assert task["state"] == "FinalReview"
        assert task["org"] == "승정원"
        assert task["output"] == "/tmp/output.md"
        assert task["now"] == "기능 구현 완료"
        assert any("검토 요청" in entry.get("remark", "") for entry in task["flow_log"])
    finally:
        kb.TASKS_FILE = original


def test_done_rejects_incomplete_todos(tmp_path):
    """cmd_done should be rejected when todos are still incomplete."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text(json.dumps([
        {
            "id": "T-4B",
            "title": "done gate test",
            "state": "InProgress",
            "org": "공조",
            "flow_log": [],
            "todos": [
                {"id": "1", "title": "완료된 항목", "status": "completed"},
                {"id": "2", "title": "미완료 항목", "status": "in-progress"},
            ],
        }
    ], ensure_ascii=False), encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_done("T-4B", "/tmp/output.md", "조기 마감 시도")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        task = tasks[0]
        assert task["state"] == "InProgress"
        assert task.get("output", "") in ("", None)
        assert task.get("flow_log", []) == []
    finally:
        kb.TASKS_FILE = original


def test_progress(tmp_path):
    """cmd_progress updates now text and appends to progress_log."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text(json.dumps([
        {"id": "T-5", "title": "progress test", "state": "InProgress", "org": "공조"}
    ], ensure_ascii=False), encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_progress("T-5", "핵심 모듈 구현 중", "요구사항 분석 완료✅|코드 작성 중🔄|테스트 대기")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        task = tasks[0]
        assert task["now"] == "핵심 모듈 구현 중"
        assert len(task.get("progress_log", [])) == 1
        todos = task.get("todos", [])
        assert len(todos) == 3
        statuses = {td["title"]: td["status"] for td in todos}
        assert statuses["요구사항 분석 완료"] == "completed"
        assert statuses["코드 작성 중"] == "in-progress"
        assert statuses["테스트 대기"] == "not-started"
    finally:
        kb.TASKS_FILE = original


def test_todo(tmp_path):
    """cmd_todo adds and updates sub-tasks."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text(json.dumps([
        {"id": "T-6", "title": "todo test", "state": "InProgress"}
    ], ensure_ascii=False), encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_todo("T-6", "1", "로그인 API 구현", "in-progress")
        kb.cmd_todo("T-6", "2", "테스트 작성", "not-started")
        kb.cmd_todo("T-6", "1", "", "completed")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        task = tasks[0]
        todos = {td["id"]: td for td in task.get("todos", [])}
        assert todos["1"]["status"] == "completed"
        assert todos["2"]["status"] == "not-started"
    finally:
        kb.TASKS_FILE = original


def test_progress_log_capped(tmp_path):
    """progress_log should not exceed MAX_PROGRESS_LOG entries."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text(json.dumps([
        {"id": "T-7", "title": "진행 로그 상한 테스트", "state": "InProgress", "org": "예조"}
    ], ensure_ascii=False), encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        for i in range(kb.MAX_PROGRESS_LOG + 5):
            kb.cmd_progress("T-7", f"{i}차 진행 상황 보고 — 현재 집행 내용 설명")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        task = tasks[0]
        assert len(task.get("progress_log", [])) == kb.MAX_PROGRESS_LOG
    finally:
        kb.TASKS_FILE = original


def test_create_uses_korean_default_order_wording(tmp_path):
    """기본 생성 문구는 한국어 기준의 어명 표현을 사용해야 한다."""
    tasks_file = tmp_path / "tasks_source.json"
    tasks_file.write_text("[]", encoding="utf-8")

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_create("TEST-ORDER-001", "사용자 인증 흐름 정리", "HongmungwanDraft", "홍문관", "홍문관제학")
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        task = next(t for t in tasks if t["id"] == "TEST-ORDER-001")
        assert task["now"] == "어명 접수, 홍문관 확인 대기"
        assert task["flow_log"][0]["remark"] == "어명 하달: 사용자 인증 흐름 정리"
    finally:
        kb.TASKS_FILE = original


def test_kanban_cli_help_is_korean():
    """CLI 기본 안내는 한국어 중심이어야 한다."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "kanban_update.py")],
        cwd=str(SCRIPTS.parent),
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert "칸반 작업 갱신 도구" in output
    assert "어명 접수 시" in output
    assert "看板任务更新工具" not in output
