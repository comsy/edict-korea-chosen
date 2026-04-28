"""tests for dashboard/server.py route handling"""
import pathlib
import sys

# Add project paths
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'dashboard'))
sys.path.insert(0, str(ROOT / 'scripts'))


def test_healthz(tmp_path):
    """healthz payload reports status and checks without binding a port."""
    # Create minimal data dir
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'tasks_source.json').write_text('[]')
    (data_dir / 'agent_config.json').write_text('{}')

    # Import and patch server
    import server as srv
    srv.DATA = data_dir
    srv.get_task_data_dir = lambda: data_dir

    body = srv.get_healthz_payload()

    assert body['status'] == 'ok'
    assert body['checks']['dataDir'] is True
    assert body['checks']['tasksReadable'] is True
