"""Tests for dashboard auto-dispatch error handling."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'dashboard'))
sys.path.insert(0, str(ROOT / 'scripts'))


def test_dispatch_records_missing_openclaw_cli(monkeypatch, tmp_path):
    """Missing OpenClaw CLI should become an actionable dispatch status."""
    import server as srv

    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    task_id = 'JJC-20260415-004'
    task = {
        'id': task_id,
        'title': '소규모 업무',
        'state': 'SejaFinalReview',
        'org': '세자',
        'updatedAt': '2026-04-15T15:34:16Z',
    }
    tasks_path = data_dir / 'tasks_source.json'
    tasks_path.write_text(json.dumps([task], ensure_ascii=False), encoding='utf-8')
    (data_dir / 'agent_config.json').write_text('{}', encoding='utf-8')

    monkeypatch.setattr(srv, 'DATA', data_dir)
    monkeypatch.setattr(srv, '_ACTIVE_TASK_DATA_DIR', data_dir)
    monkeypatch.setattr(srv, '_check_gateway_alive', lambda: True)
    monkeypatch.setattr(srv, '_resolve_openclaw_bin', lambda: None)
    monkeypatch.setattr(
        srv,
        'save_tasks',
        lambda tasks: tasks_path.write_text(
            json.dumps(tasks, ensure_ascii=False),
            encoding='utf-8',
        ),
    )

    class ImmediateThread:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            if self.target:
                self.target()

    monkeypatch.setattr(srv.threading, 'Thread', ImmediateThread)

    srv.dispatch_for_state(task_id, task, 'SejaFinalReview', trigger='test')

    updated = json.loads(tasks_path.read_text(encoding='utf-8'))[0]
    sched = updated['_scheduler']
    assert sched['lastDispatchStatus'] == 'openclaw-missing'
    assert 'OpenClaw CLI' in sched['lastDispatchError']
    assert '[WinError 2]' not in sched['lastDispatchError']
    assert any('OpenClaw CLI' in item['remark'] for item in updated['flow_log'])
