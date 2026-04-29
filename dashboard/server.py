#!/usr/bin/env python3
"""
3사6조 · 칸반 로컬 API 서버
Port: 7891 (--port 로 변경 가능)

Endpoints:
  GET  /                       → dashboard.html
  GET  /api/live-status        → data/live_status.json
  GET  /api/agent-config       → data/agent_config.json
  POST /api/set-model          → {agentId, model}
  GET  /api/model-change-log   → data/model_change_log.json
  GET  /api/last-result        → data/last_model_change_result.json
"""
import json, pathlib, subprocess, sys, threading, argparse, datetime, logging, re, os, socket, shutil
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# JWT 인증 모듈
from auth import init as auth_init, requires_auth, extract_token, verify_token, \
    is_enabled as auth_enabled, is_configured as auth_configured, \
    setup_password, verify_password, create_token

# 파일 잠금 도구 도입, 다른 스크립트와의 동시성 안전성 확보
scripts_dir = str(pathlib.Path(__file__).parent.parent / 'scripts')
sys.path.insert(0, scripts_dir)
from file_lock import atomic_json_read, atomic_json_write, atomic_json_update
from utils import validate_url, read_json, now_iso
from court_discuss import (
    create_session as cd_create, advance_discussion as cd_advance,
    get_session as cd_get, conclude_session as cd_conclude,
    list_sessions as cd_list, destroy_session as cd_destroy,
    get_fate_event as cd_fate, OFFICIAL_PROFILES as CD_PROFILES,
)

log = logging.getLogger('server')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

CHANNELS_DIR = pathlib.Path(__file__).parent.parent / 'edict' / 'backend' / 'app' / 'channels'
if str(CHANNELS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(CHANNELS_DIR.parent))
from channels import get_channel, get_channel_info, CHANNELS as NOTIFICATION_CHANNELS

OCLAW_HOME = pathlib.Path.home() / '.openclaw'
MAX_REQUEST_BODY = 1 * 1024 * 1024  # 1 MB
ALLOWED_ORIGIN = None  # Set via --cors; None means restrict to localhost
_DASHBOARD_PORT = 7891  # Updated at startup from --port arg
_DEFAULT_ORIGINS = {
    'http://127.0.0.1:7891', 'http://localhost:7891',
    'http://127.0.0.1:5173', 'http://localhost:5173',  # Vite dev server
}
_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$')

BASE = pathlib.Path(__file__).parent
DIST = BASE / 'dist'          # React 빌드 산출물 (npm run build)
DATA = BASE.parent / "data"
SCRIPTS = BASE.parent / 'scripts'
_ACTIVE_TASK_DATA_DIR = None

# 정적 리소스 MIME 타입
_MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.svg':  'image/svg+xml',
    '.ico':  'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf':  'font/ttf',
    '.map':  'application/json',
}


def cors_headers(h):
    req_origin = h.headers.get('Origin', '')
    if ALLOWED_ORIGIN:
        origin = ALLOWED_ORIGIN
    elif req_origin in _DEFAULT_ORIGINS:
        origin = req_origin
    else:
        origin = f'http://127.0.0.1:{_DASHBOARD_PORT}'
    h.send_header('Access-Control-Allow-Origin', origin)
    h.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    h.send_header('Access-Control-Allow-Headers', 'Content-Type')


def _iter_task_data_dirs():
    """사용 가능한 작업 데이터 디렉터리 후보 반환 (workspace 우선, 그 다음 로컬 data)."""
    dirs = [DATA]
    for p in sorted(OCLAW_HOME.glob('workspace-*/data')):
        if p.is_dir():
            dirs.append(p)
    return dirs


def _task_source_score(task_file: pathlib.Path):
    """작업 출처 점수: demo 가 아닌 작업 우선, 그 다음 작업 수, 마지막으로 파일 수정 시간."""
    try:
        tasks = atomic_json_read(task_file, [])
    except Exception:
        tasks = []
    if not isinstance(tasks, list):
        tasks = []
    non_demo = sum(1 for t in tasks if str((t or {}).get('id', '')) and not str((t or {}).get('id', '')).startswith('JJC-DEMO'))
    try:
        mtime = task_file.stat().st_mtime
    except Exception:
        mtime = 0
    return (1 if non_demo > 0 else 0, non_demo, len(tasks), mtime)


def get_task_data_dir():
    """현재 작업 데이터 디렉터리를 자동 선택하고 결과를 캐싱하여 서비스 기간 동안 안정 유지."""
    global _ACTIVE_TASK_DATA_DIR
    if _ACTIVE_TASK_DATA_DIR and _ACTIVE_TASK_DATA_DIR.is_dir():
        return _ACTIVE_TASK_DATA_DIR
    best_dir = DATA
    best_score = (-1, -1, -1, -1)
    for d in _iter_task_data_dirs():
        tf = d / 'tasks_source.json'
        if not tf.exists():
            continue
        score = _task_source_score(tf)
        if score > best_score:
            best_score = score
            best_dir = d
    _ACTIVE_TASK_DATA_DIR = best_dir
    log.info(f'작업 데이터 출처: {_ACTIVE_TASK_DATA_DIR}')
    return _ACTIVE_TASK_DATA_DIR


def load_tasks():
    task_data_dir = get_task_data_dir()
    return atomic_json_read(task_data_dir / 'tasks_source.json', [])


def save_tasks(tasks):
    task_data_dir = get_task_data_dir()
    atomic_json_write(task_data_dir / 'tasks_source.json', tasks)
    # Trigger refresh (비동기, 블로킹하지 않음, 좀비 프로세스 방지)
    script = task_data_dir.parent / 'scripts' / 'refresh_live_data.py'
    if not script.exists():
        script = SCRIPTS / 'refresh_live_data.py'

    def _refresh():
        try:
            subprocess.run(['python3', str(script)], timeout=30)
        except Exception as e:
            log.warning(f'refresh_live_data.py 트리거 실패: {e}')
    threading.Thread(target=_refresh, daemon=True).start()


def handle_task_action(task_id, action, reason):
    """Stop/cancel/resume a task from the dashboard."""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}

    old_state = task.get('state', '')
    _ensure_scheduler(task)
    _scheduler_snapshot(task, f'task-action-before-{action}')

    if action == 'stop':
        task['state'] = 'Blocked'
        task['block'] = reason or '임금 중단 지시'
        task['now'] = f'⏸️ 중단됨: {reason}'
    elif action == 'cancel':
        task['state'] = 'Cancelled'
        task['block'] = reason or '임금 취소 지시'
        task['now'] = f'🚫 취소됨: {reason}'
    elif action == 'resume':
        # Resume to previous active state or InProgress
        task['state'] = task.get('_prev_state', 'InProgress')
        task['block'] = '없음'
        task['now'] = f'▶️ 집행 재개됨'

    if action in ('stop', 'cancel'):
        task['_prev_state'] = old_state  # Save for resume

    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '임금',
        'to': task.get('org', ''),
        'remark': f'{"⏸️ 중단" if action == "stop" else "🚫 취소" if action == "cancel" else "▶️ 재개"}：{reason}'
    })

    if action == 'resume':
        _scheduler_mark_progress(task, f'복구: {task.get("state", "InProgress")}')
    else:
        _scheduler_add_flow(task, f'임금{action}：{reason or "없음"}')

    task['updatedAt'] = now_iso()

    save_tasks(tasks)
    if action == 'resume' and task.get('state') not in _TERMINAL_STATES:
        dispatch_for_state(task_id, task, task.get('state'), trigger='resume')
    label = {'stop': '중단 처리됨', 'cancel': '취소 처리됨', 'resume': '재개 처리됨'}[action]
    return {'ok': True, 'message': f'{task_id} {label}'}


def handle_archive_task(task_id, archived, archive_all_done=False):
    """Archive or unarchive a task, or batch-archive all Done/Cancelled tasks."""
    tasks = load_tasks()
    if archive_all_done:
        count = 0
        for t in tasks:
            if t.get('state') in ('Completed', 'Cancelled') and not t.get('archived'):
                t['archived'] = True
                t['archivedAt'] = now_iso()
                count += 1
        save_tasks(tasks)
        return {'ok': True, 'message': f'{count} 건 지시를 보관했습니다', 'count': count}
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}
    task['archived'] = archived
    if archived:
        task['archivedAt'] = now_iso()
    else:
        task.pop('archivedAt', None)
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    label = '보관 처리됨' if archived else '보관 해제됨'
    return {'ok': True, 'message': f'{task_id} {label}'}


def update_task_todos(task_id, todos):
    """Update the todos list for a task."""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}

    task['todos'] = todos
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    return {'ok': True, 'message': f'{task_id} 하위 작업이 업데이트되었습니다'}


def read_skill_content(agent_id, skill_name):
    """Read SKILL.md content for a specific skill."""
    # 입력 검증: 경로 탐색 방지
    if not _SAFE_NAME_RE.match(agent_id) or not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': '파라미터에 허용되지 않은 문자가 포함되었습니다'}
    cfg = read_json(DATA / 'agent_config.json', {})
    agents = cfg.get('agents', [])
    ag = next((a for a in agents if a.get('id') == agent_id), None)
    if not ag:
        return {'ok': False, 'error': f'Agent {agent_id}이(가) 존재하지 않습니다'}
    sk = next((s for s in ag.get('skills', []) if s.get('name') == skill_name), None)
    if not sk:
        return {'ok': False, 'error': f'스킬 {skill_name}이(가) 존재하지 않습니다'}
    skill_path = pathlib.Path(sk.get('path', '')).resolve()
    # 경로 탐색 보호: 경로가 OCLAW_HOME 또는 프로젝트 디렉터리 안에 있는지 확인
    allowed_roots = (OCLAW_HOME.resolve(), BASE.parent.resolve())
    if not any(str(skill_path).startswith(str(root)) for root in allowed_roots):
        return {'ok': False, 'error': '허용된 디렉터리 범위를 벗어난 경로입니다'}
    if not skill_path.exists():
        return {'ok': True, 'name': skill_name, 'agent': agent_id, 'content': '(SKILL.md 파일이 존재하지 않습니다)', 'path': str(skill_path)}
    try:
        content = skill_path.read_text()
        return {'ok': True, 'name': skill_name, 'agent': agent_id, 'content': content, 'path': str(skill_path)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def add_skill_to_agent(agent_id, skill_name, description, trigger=''):
    """Create a new skill for an agent with a standardised SKILL.md template."""
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skill_name 필드에 허용되지 않은 문자가 있습니다: {skill_name}'}
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 필드에 허용되지 않은 문자가 있습니다: {agent_id}'}
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    workspace.mkdir(parents=True, exist_ok=True)
    skill_md = workspace / 'SKILL.md'
    desc_line = description or skill_name
    trigger_section = f'\n## 트리거 조건\n{trigger}\n' if trigger else ''
    template = (f'---\n'
                f'name: {skill_name}\n'
                f'description: {desc_line}\n'
                f'---\n\n'
                f'# {skill_name}\n\n'
                f'{desc_line}\n'
                f'{trigger_section}\n'
                f'## 입력\n\n'
                f'<!-- 이 스킬이 받는 입력을 작성하세요 -->\n\n'
                f'## 처리 절차\n\n'
                f'1. 1단계\n'
                f'2. 2단계\n\n'
                f'## 출력 규격\n\n'
                f'<!-- 산출물 형식과 전달 기준을 작성하세요 -->\n\n'
                f'## 주의사항\n\n'
                f'- (제약, 제한, 특수 규칙을 여기에 추가하세요)\n')
    skill_md.write_text(template)
    # Re-sync agent config
    try:
        subprocess.run(['python3', str(SCRIPTS / 'sync_agent_config.py')], timeout=10)
    except Exception:
        pass
    return {'ok': True, 'message': f'스킬 {skill_name} 을(를) 추가했습니다: {agent_id}', 'path': str(skill_md)}


def add_remote_skill(agent_id, skill_name, source_url, description=''):
    """원격 URL 또는 로컬 경로에서 Agent 의 skill SKILL.md 파일을 추가합니다.
    
    지원되는 출처:
    - HTTPS URLs: https://raw.githubusercontent.com/...
    - 로컬 경로: /path/to/SKILL.md 또는 file:///path/to/SKILL.md
    """
    # 입력 검증
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 필드에 허용되지 않은 문자가 있습니다: {agent_id}'}
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skillName 필드에 허용되지 않은 문자가 있습니다: {skill_name}'}
    if not source_url or not isinstance(source_url, str):
        return {'ok': False, 'error': 'sourceUrl은 유효한 문자열이어야 합니다'}
    
    source_url = source_url.strip()
    
    # Agent 존재 여부 확인
    cfg = read_json(DATA / 'agent_config.json', {})
    agents = cfg.get('agents', [])
    if not any(a.get('id') == agent_id for a in agents):
        return {'ok': False, 'error': f'Agent {agent_id}이(가) 존재하지 않습니다'}
    
    # 파일 내용 다운로드 또는 읽기
    try:
        if source_url.startswith('http://') or source_url.startswith('https://'):
            # HTTPS URL 검증
            if not validate_url(source_url, allowed_schemes=('https',)):
                return {'ok': False, 'error': 'URL이 유효하지 않거나 안전하지 않습니다 (HTTPS만 지원)'}
            
            # URL 에서 다운로드, 타임아웃 보호 포함
            req = Request(source_url, headers={'User-Agent': 'OpenClaw-SkillManager/1.0'})
            try:
                resp = urlopen(req, timeout=10)
                content = resp.read(10 * 1024 * 1024).decode('utf-8')  # 최대 10MB
                if len(content) > 10 * 1024 * 1024:
                    return {'ok': False, 'error': '파일이 너무 큽니다 (최대 10MB)'}
            except Exception as e:
                return {'ok': False, 'error': f'URL에 접근할 수 없습니다: {str(e)[:100]}'}
        
        elif source_url.startswith('file://'):
            # file:// URL 형식
            local_path = pathlib.Path(source_url[7:]).resolve()
            if not local_path.exists():
                return {'ok': False, 'error': f'로컬 파일이 존재하지 않습니다: {local_path}'}
            # 경로 탐색 방지: 로컬 경로 분기와 동일하게, 허용 범위 내인지 확인
            allowed_roots = (OCLAW_HOME.resolve(), BASE.parent.resolve())
            if not any(str(local_path).startswith(str(root)) for root in allowed_roots):
                return {'ok': False, 'error': '허용된 디렉터리 범위를 벗어난 경로입니다'}
            content = local_path.read_text()
        
        elif source_url.startswith('/') or source_url.startswith('.'):
            # 로컬 절대 또는 상대 경로
            local_path = pathlib.Path(source_url).resolve()
            if not local_path.exists():
                return {'ok': False, 'error': f'로컬 파일이 존재하지 않습니다: {local_path}'}
            # 경로 탐색 방지
            allowed_roots = (OCLAW_HOME.resolve(), BASE.parent.resolve())
            if not any(str(local_path).startswith(str(root)) for root in allowed_roots):
                return {'ok': False, 'error': '허용된 디렉터리 범위를 벗어난 경로입니다'}
            content = local_path.read_text()
        
        else:
            return {'ok': False, 'error': '지원하지 않는 URL 형식입니다 (https://, file://, 로컬 경로만 지원)'}
    except Exception as e:
        return {'ok': False, 'error': f'파일 읽기에 실패했습니다: {str(e)[:100]}'}
    
    # 기본 검증: Markdown 형식이며 YAML frontmatter 포함 여부 확인
    if not content.startswith('---'):
        return {'ok': False, 'error': '파일 형식이 올바르지 않습니다 (YAML frontmatter 누락)'}
    
    # frontmatter 구조 검증 (문자열 검사 후 YAML 파싱 시도)
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {'ok': False, 'error': '파일 형식이 올바르지 않습니다 (YAML frontmatter 구조 오류)'}
    if 'name:' not in content[:500]:
        return {'ok': False, 'error': '파일 형식이 올바르지 않습니다: frontmatter에 name 필드가 없습니다'}
    try:
        import yaml
        yaml.safe_load(parts[1])  # YAML 문법 엄격 검증
    except ImportError:
        pass  # PyYAML 미설치, 엄격 검증 건너뜀, 문자열 검사는 통과
    except Exception as e:
        return {'ok': False, 'error': f'YAML 형식이 올바르지 않습니다: {str(e)[:100]}'}
    
    # 로컬 디렉터리 생성
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    workspace.mkdir(parents=True, exist_ok=True)
    skill_md = workspace / 'SKILL.md'
    
    # SKILL.md 작성
    skill_md.write_text(content)
    
    # 출처 정보를 .source.json 에 저장
    source_info = {
        'skillName': skill_name,
        'sourceUrl': source_url,
        'description': description,
        'addedAt': now_iso(),
        'lastUpdated': now_iso(),
        'checksum': _compute_checksum(content),
        'status': 'valid',
    }
    source_json = workspace / '.source.json'
    source_json.write_text(json.dumps(source_info, ensure_ascii=False, indent=2))
    
    # Re-sync agent config
    try:
        subprocess.run(['python3', str(SCRIPTS / 'sync_agent_config.py')], timeout=10)
    except Exception:
        pass
    
    return {
        'ok': True,
        'message': f'스킬 {skill_name} 원격 소스에서 추가했습니다: {agent_id}',
        'skillName': skill_name,
        'agentId': agent_id,
        'source': source_url,
        'localPath': str(skill_md),
        'size': len(content),
        'addedAt': now_iso(),
    }


def get_remote_skills_list():
    """추가된 모든 원격 skills 및 출처 정보 목록"""
    remote_skills = []
    
    # 모든 workspace 순회
    for ws_dir in OCLAW_HOME.glob('workspace-*'):
        agent_id = ws_dir.name.replace('workspace-', '')
        skills_dir = ws_dir / 'skills'
        if not skills_dir.exists():
            continue
        
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            source_json = skill_dir / '.source.json'
            skill_md = skill_dir / 'SKILL.md'
            
            if not source_json.exists():
                # 로컬에서 생성된 skill 건너뜀
                continue
            
            try:
                source_info = json.loads(source_json.read_text())
                # SKILL.md 존재 여부 확인
                status = 'valid' if skill_md.exists() else 'not-found'
                remote_skills.append({
                    'skillName': skill_name,
                    'agentId': agent_id,
                    'sourceUrl': source_info.get('sourceUrl', ''),
                    'description': source_info.get('description', ''),
                    'localPath': str(skill_md),
                    'addedAt': source_info.get('addedAt', ''),
                    'lastUpdated': source_info.get('lastUpdated', ''),
                    'status': status,
                })
            except Exception:
                pass
    
    return {
        'ok': True,
        'remoteSkills': remote_skills,
        'count': len(remote_skills),
        'listedAt': now_iso(),
    }


def update_remote_skill(agent_id, skill_name):
    """추가된 원격 skill 을 최신 버전으로 업데이트 (출처 URL 에서 다시 다운로드)"""
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 필드에 허용되지 않은 문자가 있습니다: {agent_id}'}
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skillName 필드에 허용되지 않은 문자가 있습니다: {skill_name}'}
    
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    source_json = workspace / '.source.json'
    skill_md = workspace / 'SKILL.md'
    
    if not source_json.exists():
        return {'ok': False, 'error': f'스킬 {skill_name} 은(는) 원격 skill 이 아닙니다 (.source.json 없음)'}
    
    try:
        source_info = json.loads(source_json.read_text())
        source_url = source_info.get('sourceUrl', '')
        if not source_url:
            return {'ok': False, 'error': '출처 URL이(가) 존재하지 않습니다'}
        
        # 다시 다운로드
        result = add_remote_skill(agent_id, skill_name, source_url, 
                                  source_info.get('description', ''))
        if result['ok']:
            result['message'] = f'스킬을 업데이트했습니다'
            source_info_updated = json.loads(source_json.read_text())
            result['newVersion'] = source_info_updated.get('checksum', 'unknown')
        return result
    except Exception as e:
        return {'ok': False, 'error': f'업데이트 실패: {str(e)[:100]}'}


def remove_remote_skill(agent_id, skill_name):
    """추가된 원격 skill 제거"""
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 필드에 허용되지 않은 문자가 있습니다: {agent_id}'}
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skillName 필드에 허용되지 않은 문자가 있습니다: {skill_name}'}
    
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    if not workspace.exists():
        return {'ok': False, 'error': f'스킬이 존재하지 않습니다: {skill_name}'}
    
    # 원격 skill 여부 확인
    source_json = workspace / '.source.json'
    if not source_json.exists():
        return {'ok': False, 'error': f'스킬 {skill_name} 은(는) 원격 스킬이 아니므로 이 API로 제거할 수 없습니다'}
    
    try:
        # skill 디렉터리 전체 삭제
        import shutil
        shutil.rmtree(workspace)
        
        # Re-sync agent config
        try:
            subprocess.run(['python3', str(SCRIPTS / 'sync_agent_config.py')], timeout=10)
        except Exception:
            pass
        
        return {'ok': True, 'message': f'스킬 {skill_name} 에서 제거되었습니다: {agent_id} 제거'}
    except Exception as e:
        return {'ok': False, 'error': f'제거 실패: {str(e)[:100]}'}


def _compute_checksum(content: str) -> str:
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def migrate_notification_config():
    """기존 설정 (feishu_webhook) 을 새 구조 (notification) 로 자동 마이그레이션"""
    cfg_path = DATA / 'morning_brief_config.json'
    cfg = read_json(cfg_path, {})
    if not cfg:
        return
    if 'notification' in cfg:
        return
    if 'feishu_webhook' not in cfg:
        return
    webhook = cfg.get('feishu_webhook', '').strip()
    cfg['notification'] = {
        'enabled': bool(webhook),
        'channel': 'feishu',
        'webhook': webhook
    }
    try:
        atomic_json_write(cfg_path, cfg)
        log.info('feishu_webhook을 notification 설정으로 자동 마이그레이션했습니다')
    except Exception as e:
        log.warning(f'설정 마이그레이션 실패: {e}')


def push_notification():
    """범용 메시지 푸시 (다채널 지원)"""
    cfg = read_json(DATA / 'morning_brief_config.json', {})
    notification = cfg.get('notification', {})
    if not notification and cfg.get('feishu_webhook'):
        notification = {'enabled': True, 'channel': 'feishu', 'webhook': cfg['feishu_webhook']}
    if not notification.get('enabled', True):
        return
    channel_type = notification.get('channel', 'feishu')
    webhook = notification.get('webhook', '').strip()
    if not webhook:
        return
    channel_cls = get_channel(channel_type)
    if not channel_cls:
        log.warning(f'알 수 없는 알림 채널: {channel_type}')
        return
    if not channel_cls.validate_webhook(webhook):
        log.warning(f'{channel_cls.label} Webhook URL이 유효하지 않습니다: {webhook}')
        return
    brief = read_json(DATA / 'morning_brief.json', {})
    date_str = brief.get('date', '')
    total = sum(len(v) for v in (brief.get('categories') or {}).values())
    if not total:
        return
    cat_lines = []
    for cat, items in (brief.get('categories') or {}).items():
        if items:
            cat_lines.append(f'  {cat}: {len(items)} 건')
    summary = '\n'.join(cat_lines)
    date_fmt = date_str[:4] + '-' + date_str[4:6] + '-' + date_str[6:] + '' if len(date_str) == 8 else date_str
    title = f'📰 조보 요약 · {date_fmt}'
    content = f'총 **{total}**건 조보 요약이 업데이트되었습니다\n{summary}'
    url = f'http://127.0.0.1:{_DASHBOARD_PORT}'
    success = channel_cls.send(webhook, title, content, url)
    print(f'[{channel_cls.label}] 전송{"성공" if success else "실패"}')


def push_to_feishu():
    """Push morning brief link to Feishu via webhook. (사용 중단, push_notification 사용)"""
    push_notification()


# 지시 제목 최소 요건
_MIN_TITLE_LEN = 6
_JUNK_TITLES = {
    '?', '？', '好', '好的', '是', '否', '不', '不是', '对', '了解', '收到',
    '嗯', '哦', '知道了', '开启了么', '可以', '不行', '行', 'ok', 'yes', 'no',
    '你去开启', '测试', '试试', '看看',
}


def handle_create_task(title, org='홍문관', official='홍문관', priority='normal', template_id='', params=None, target_dept=''):
    """칸반에서 신규 작업 생성 (성지 템플릿으로 지시 발령)."""
    if not title or not title.strip():
        return {'ok': False, 'error': '작업 제목은 비어 있을 수 없습니다'}
    title = title.strip()
    # Conversation info 메타데이터 제거
    title = re.split(r'\n*Conversation info\s*\(', title, maxsplit=1)[0].strip()
    title = re.split(r'\n*```', title, maxsplit=1)[0].strip()
    # 자주 쓰이는 접두사 정리: "传旨:" "下旨:" 등
    title = re.sub(r'^(传旨|下旨)[：:\uff1a]\s*', '', title)
    if len(title) > 100:
        title = title[:100] + '…'
    # 제목 품질 검증: 잡담이 지시로 오인되어 등록되지 않도록 함
    if len(title) < _MIN_TITLE_LEN:
        return {'ok': False, 'error': f'제목이 너무 짧습니다 ({len(title)}<{_MIN_TITLE_LEN}자) 지시로 보기 어렵습니다'}
    if title.lower() in _JUNK_TITLES:
        return {'ok': False, 'error': f'「{title}」은(는) 유효한 지시가 아닙니다. 구체적인 작업 지시를 입력해 주세요'}
    # task id 생성: JJC-YYYYMMDD-NNN
    today = datetime.datetime.now().strftime('%Y%m%d')
    tasks = load_tasks()
    today_ids = [t['id'] for t in tasks if t.get('id', '').startswith(f'JJC-{today}-')]
    seq = 1
    if today_ids:
        nums = [int(tid.split('-')[-1]) for tid in today_ids if tid.split('-')[-1].isdigit()]
        seq = max(nums) + 1 if nums else 1
    task_id = f'JJC-{today}-{seq:03d}'
    # 표준 시작점: 임금 -> 세자 분류
    # target_dept 는 템플릿 권장 집행 부서(승정원 배분 참고용)
    initial_org = '세자'
    new_task = {
        'id': task_id,
        'title': title,
        'official': official,
        'org': initial_org,
        'state': 'SejaFinalReview',
        'now': '세자 검토 대기',
        'eta': '-',
        'block': '없음',
        'output': '',
        'ac': '',
        'priority': priority,
        'templateId': template_id,
        'templateParams': params or {},
        'flow_log': [{
            'at': now_iso(),
            'from': '임금',
            'to': initial_org,
            'remark': f'지시 등록: {title}'
        }],
        'updatedAt': now_iso(),
    }
    if target_dept:
        new_task['targetDept'] = target_dept

    _ensure_scheduler(new_task)
    _scheduler_snapshot(new_task, 'create-task-initial')
    _scheduler_mark_progress(new_task, '작업 생성')

    tasks.insert(0, new_task)
    save_tasks(tasks)
    log.info(f'작업 생성: {task_id} | {title[:40]}')

    dispatch_for_state(task_id, new_task, 'SejaFinalReview', trigger='imperial-edict')

    return {'ok': True, 'taskId': task_id, 'message': f'지시 {task_id} 등록 완료, 세자에게 전달 중'}


def _todo_progress(task):
    todos = task.get('todos') or []
    total = len(todos)
    completed = sum(1 for td in todos if td.get('status') == 'completed')
    return completed, total


def handle_review_action(task_id, action, comment=''):
    """사간원 심의: 승인/반려."""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}
    if task.get('state') not in ('FinalReview', 'SaganwonFinalReview'):
        return {'ok': False, 'error': f'작업 {task_id} 현재 상태가 {task.get("state")} 이라 심의를 진행할 수 없습니다'}

    _ensure_scheduler(task)
    _scheduler_snapshot(task, f'review-before-{action}')

    if action == 'approve':
        if task['state'] == 'SaganwonFinalReview':
            task['state'] = 'SeungjeongwonAssigned'
            task['now'] = '사간원 승인, 승정원 배분 단계로 이동'
            remark = f'✅ 승인: {comment or "사간원 심의 통과"}'
            to_dept = '승정원'
        else:  # FinalReview
            completed, total = _todo_progress(task)
            if total > 0 and completed < total:
                return {'ok': False, 'error': f'하위 작업이 아직 모두 완료되지 않았습니다 ({completed}/{total}), 지금은 완료할 수 없습니다'}
            task['state'] = 'Completed'
            task['now'] = '검토 승인, 작업 완료'
            remark = f'✅ 최종 승인: {comment or "검토 통과"}'
            to_dept = '임금'
    elif action == 'reject':
        round_num = (task.get('review_round') or 0) + 1
        task['review_round'] = round_num
        task['state'] = 'HongmungwanDraft'
        task['now'] = f'반려 후 홍문관 수정 요청 ({round_num}차)'
        remark = f'🚫 반려: {comment or "수정 필요"}'
        to_dept = '홍문관'
    else:
        return {'ok': False, 'error': f'알 수 없는 동작: {action}'}

    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '사간원' if task.get('state') != 'Completed' else '임금',
        'to': to_dept,
        'remark': remark
    })
    _scheduler_mark_progress(task, f'심의 동작 {action} -> {task.get("state")}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    # 🚀 심의 이후 해당 Agent 자동 배분
    new_state = task['state']
    if new_state not in ('Completed',):
        dispatch_for_state(task_id, task, new_state)

    label = '승인 완료' if action == 'approve' else '반려 완료'
    dispatched = ' (Agent 자동 배분 완료)' if new_state != 'Completed' else ''
    return {'ok': True, 'message': f'{task_id} {label}{dispatched}'}


# ══ Agent 온라인 상태 감지 ══

_AGENT_DEPTS = [
    {'id':'seja',   'label':'세자',  'emoji':'🤴', 'role':'중앙 허브', 'rank':'중앙'},
    {'id':'hongmungwan','label':'홍문관','emoji':'📜', 'role':'기획',      'rank':'중앙'},
    {'id':'saganwon',  'label':'사간원','emoji':'🔍', 'role':'심의',      'rank':'중앙'},
    {'id':'seungjeongwon','label':'승정원','emoji':'📮', 'role':'배분',      'rank':'중앙'},
    {'id':'hojo',    'label':'호조',  'emoji':'💰', 'role':'데이터',    'rank':'집행'},
    {'id':'yejo',    'label':'예조',  'emoji':'📝', 'role':'문서',      'rank':'집행'},
    {'id':'byeongjo',  'label':'병조',  'emoji':'⚔️', 'role':'구현',      'rank':'집행'},
    {'id':'hyeongjo',  'label':'형조',  'emoji':'⚖️', 'role':'검토',      'rank':'집행'},
    {'id':'gongjo',  'label':'공조',  'emoji':'🔧', 'role':'인프라',    'rank':'집행'},
    {'id':'ijo',     'label':'이조',  'emoji':'👔', 'role':'인사/교육', 'rank':'집행'},
    {'id':'jobocheong',     'label':'조보청','emoji':'📰', 'role':'브리핑',    'rank':'보조'},
    {'id':'gwansanggam', 'label':'관상감','emoji':'🔭', 'role':'관측/분석', 'rank':'보조'},
]


def _check_gateway_alive():
    """Gateway 가 실행 중인지 감지.

    Windows 에서는 pgrep 에 의존하지 않음; 로컬 포트 프로빙으로 우선 판단.
    """
    if _check_gateway_probe():
        return True
    try:
        if os.name == 'nt':
            with socket.create_connection(('127.0.0.1', 18789), timeout=2):
                return True
            return False
        result = subprocess.run(['pgrep', '-f', 'openclaw-gateway'],
                                capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def _check_gateway_probe():
    """HTTP probe 로 Gateway 응답 여부 감지."""
    for url in ('http://127.0.0.1:18789/', 'http://127.0.0.1:18789/healthz'):
        try:
            from urllib.request import urlopen
            resp = urlopen(url, timeout=3)
            if 200 <= resp.status < 500:
                return True
        except Exception:
            continue
    return False


def _get_agent_session_status(agent_id):
    """Agent 의 sessions.json 을 읽어 활성 상태 획득.
    반환: (last_active_ts_ms, session_count, is_busy)
    """
    sessions_file = OCLAW_HOME / 'agents' / agent_id / 'sessions' / 'sessions.json'
    if not sessions_file.exists():
        return 0, 0, False
    try:
        data = json.loads(sessions_file.read_text())
        if not isinstance(data, dict):
            return 0, 0, False
        session_count = len(data)
        last_ts = 0
        for v in data.values():
            ts = v.get('updatedAt', 0)
            if isinstance(ts, (int, float)) and ts > last_ts:
                last_ts = ts
        now_ms = int(datetime.datetime.now().timestamp() * 1000)
        age_ms = now_ms - last_ts if last_ts else 9999999999
        is_busy = age_ms <= 2 * 60 * 1000  # 2분 이내면 작업 중으로 간주
        return last_ts, session_count, is_busy
    except Exception:
        return 0, 0, False


def _check_agent_process(agent_id):
    """해당 Agent 의 openclaw-agent 프로세스 실행 여부 감지."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', f'openclaw.*--agent.*{agent_id}'],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_agent_workspace(agent_id):
    """Agent 작업 공간 존재 여부 확인."""
    ws = OCLAW_HOME / f'workspace-{agent_id}'
    return ws.is_dir()


def get_agents_status():
    """모든 Agent 의 온라인 상태 획득.
    각 Agent 의 다음 정보 반환:
    - status: 'running' | 'idle' | 'offline' | 'unconfigured'
    - lastActive: 마지막 활성 시각
    - sessions: 세션 수
    - hasWorkspace: 작업 공간 존재 여부
    - processAlive: 프로세스 실행 여부
    """
    gateway_alive = _check_gateway_alive()
    gateway_probe = _check_gateway_probe() if gateway_alive else False

    agents = []
    seen_ids = set()
    for dept in _AGENT_DEPTS:
        aid = dept['id']
        if aid in seen_ids:
            continue
        seen_ids.add(aid)

        has_workspace = _check_agent_workspace(aid)
        last_ts, sess_count, is_busy = _get_agent_session_status(aid)
        process_alive = _check_agent_process(aid)

        # 상태 판정
        if not has_workspace:
            status = 'unconfigured'
            status_label = '❌ 미설정'
        elif not gateway_alive:
            status = 'offline'
            status_label = '🔴 Gateway 오프라인'
        elif process_alive or is_busy:
            status = 'running'
            status_label = '🟢 실행 중'
        elif last_ts > 0:
            now_ms = int(datetime.datetime.now().timestamp() * 1000)
            age_ms = now_ms - last_ts
            if age_ms <= 10 * 60 * 1000:  # 10분 이내
                status = 'idle'
                status_label = '🟡 대기'
            elif age_ms <= 3600 * 1000:  # 1시간 이내
                status = 'idle'
                status_label = '⚪ 유휴'
            else:
                status = 'idle'
                status_label = '⚪ 슬립'
        else:
            status = 'idle'
            status_label = '⚪ 기록 없음'

        # 마지막 활성 시각 포맷
        last_active_str = None
        if last_ts > 0:
            try:
                last_active_str = datetime.datetime.fromtimestamp(
                    last_ts / 1000
                ).strftime('%m-%d %H:%M')
            except Exception:
                pass

        agents.append({
            'id': aid,
            'label': dept['label'],
            'emoji': dept['emoji'],
            'role': dept['role'],
            'status': status,
            'statusLabel': status_label,
            'lastActive': last_active_str,
            'lastActiveTs': last_ts,
            'sessions': sess_count,
            'hasWorkspace': has_workspace,
            'processAlive': process_alive,
        })

    return {
        'ok': True,
        'gateway': {
            'alive': gateway_alive,
            'probe': gateway_probe,
            'status': '🟢 실행 중' if gateway_probe else ('🟡 프로세스는 있으나 응답 없음' if gateway_alive else '🔴 미실행'),
        },
        'agents': agents,
        'checkedAt': now_iso(),
    }


def wake_agent(agent_id, message=''):
    """지정된 Agent 깨우기, 하트비트/깨움 메시지 전송."""
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agent_id가 올바르지 않습니다: {agent_id}'}
    if not _check_agent_workspace(agent_id):
        return {'ok': False, 'error': f'{agent_id} 작업공간이 없습니다. 먼저 구성해 주세요'}
    if not _check_gateway_alive():
        return {'ok': False, 'error': 'Gateway가 실행 중이 아닙니다. 먼저 openclaw gateway start를 실행해 주세요'}

    # agent_id 를 그대로 runtime_id 로 사용 (openclaw agents list 의 등록명)
    runtime_id = agent_id
    msg = message or f'🔔 시스템 하트비트 점검 - 온라인이면 OK로 응답해 주세요. 현재 시각: {now_iso()}'

    def do_wake():
        try:
            cmd = ['openclaw', 'agent', '--agent', runtime_id, '-m', msg, '--timeout', '120']
            log.info(f'🔔 {agent_id} 깨우기 시도...')
            # 재시도 포함 (최대 2회)
            for attempt in range(1, 3):
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=130)
                if result.returncode == 0:
                    log.info(f'✅ {agent_id} 깨우기 성공')
                    return
                err_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
                log.warning(f'⚠️ {agent_id} 깨우기 실패({attempt}회차): {err_msg}')
                if attempt < 2:
                    import time
                    time.sleep(5)
            log.error(f'❌ {agent_id} 깨우기 최종 실패')
        except subprocess.TimeoutExpired:
            log.error(f'❌ {agent_id} 깨우기 시간 초과(130s)')
        except Exception as e:
            log.warning(f'⚠️ {agent_id} 깨우기 예외: {e}')
    threading.Thread(target=do_wake, daemon=True).start()

    return {'ok': True, 'message': f'{agent_id} 깨우기 신호를 보냈습니다. 약 10-30초 후 반영됩니다'}


# ══ Agent 실시간 활동 읽기 ══

# 상태 → agent_id 매핑
_STATE_AGENT_MAP = {
    'SejaFinalReview': 'seja',
    'HongmungwanDraft': 'hongmungwan',
    'SaganwonFinalReview': 'saganwon',
    'SeungjeongwonAssigned': 'seungjeongwon',
    'InProgress': None,     # 6조, org 에서 추론 필요
    'FinalReview': 'seungjeongwon',
    'Ready': None,          # 실행 대기, org 에서 추론
    'Pending': 'hongmungwan',
}
_ORG_AGENT_MAP = {
    '예조': 'yejo', '호조': 'hojo', '병조': 'byeongjo',
    '형조': 'hyeongjo', '공조': 'gongjo', '이조': 'ijo',
    '홍문관': 'hongmungwan', '사간원': 'saganwon', '승정원': 'seungjeongwon',
    '조보청': 'jobocheong', '관상감': 'gwansanggam',
}

_TERMINAL_STATES = {'Completed', 'Cancelled'}


def _parse_iso(ts):
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        return None


def _ensure_scheduler(task):
    sched = task.setdefault('_scheduler', {})
    if not isinstance(sched, dict):
        sched = {}
        task['_scheduler'] = sched
    sched.setdefault('enabled', True)
    sched.setdefault('stallThresholdSec', 600)
    sched.setdefault('maxRetry', 2)
    sched.setdefault('retryCount', 0)
    sched.setdefault('escalationLevel', 0)
    sched.setdefault('autoRollback', True)
    if not sched.get('lastProgressAt'):
        sched['lastProgressAt'] = task.get('updatedAt') or now_iso()
    if 'stallSince' not in sched:
        sched['stallSince'] = None
    if 'lastDispatchStatus' not in sched:
        sched['lastDispatchStatus'] = 'idle'
    if 'snapshot' not in sched:
        sched['snapshot'] = {
            'state': task.get('state', ''),
            'org': task.get('org', ''),
            'now': task.get('now', ''),
            'savedAt': now_iso(),
            'note': 'init',
        }
    return sched


def _scheduler_add_flow(task, remark, to=''):
    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '세자 조정',
        'to': to or task.get('org', ''),
        'remark': f'🧭 {remark}'
    })


def _scheduler_snapshot(task, note=''):
    sched = _ensure_scheduler(task)
    sched['snapshot'] = {
        'state': task.get('state', ''),
        'org': task.get('org', ''),
        'now': task.get('now', ''),
        'savedAt': now_iso(),
        'note': note or 'snapshot',
    }


def _scheduler_mark_progress(task, note=''):
    sched = _ensure_scheduler(task)
    sched['lastProgressAt'] = now_iso()
    sched['stallSince'] = None
    sched['retryCount'] = 0
    sched['escalationLevel'] = 0
    sched['rollbackCount'] = 0
    sched['lastEscalatedAt'] = None
    if note:
        _scheduler_add_flow(task, f'진행 확인: {note}')


def _resolve_openclaw_bin():
    """Return the OpenClaw CLI path used by dashboard dispatch.

    On Windows, npm-installed CLIs are commonly exposed as .cmd shims.  Using
    shutil.which lets Python resolve that shim before subprocess runs.
    """
    configured = os.environ.get('OPENCLAW_BIN', '').strip()
    if configured:
        return configured
    return shutil.which('openclaw')


def _update_task_scheduler(task_id, updater):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return False
    sched = _ensure_scheduler(task)
    updater(task, sched)
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    return True


def get_scheduler_state(task_id):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}
    sched = _ensure_scheduler(task)
    last_progress = _parse_iso(sched.get('lastProgressAt') or task.get('updatedAt'))
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    stalled_sec = 0
    if last_progress:
        stalled_sec = max(0, int((now_dt - last_progress).total_seconds()))
    return {
        'ok': True,
        'taskId': task_id,
        'state': task.get('state', ''),
        'org': task.get('org', ''),
        'scheduler': sched,
        'stalledSec': stalled_sec,
        'checkedAt': now_iso(),
    }


def handle_scheduler_retry(task_id, reason=''):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}
    state = task.get('state', '')
    if state in _TERMINAL_STATES or state == 'Blocked':
        return {'ok': False, 'error': f'작업 {task_id} 현재 상태 {state}에서는 재시도를 지원하지 않습니다'}

    sched = _ensure_scheduler(task)
    sched['retryCount'] = int(sched.get('retryCount') or 0) + 1
    sched['lastRetryAt'] = now_iso()
    sched['lastDispatchTrigger'] = 'seja-retry'
    _scheduler_add_flow(task, f'재시도 {sched["retryCount"]}회: {reason or "시간 초과로 미진행"}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    dispatch_for_state(task_id, task, state, trigger='seja-retry')
    return {'ok': True, 'message': f'{task_id} 재시도 배분을 시작했습니다', 'retryCount': sched['retryCount']}


def handle_scheduler_escalate(task_id, reason=''):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}
    state = task.get('state', '')
    if state in _TERMINAL_STATES:
        return {'ok': False, 'error': f'작업 {task_id} 은(는) 종료되어 상향이 필요 없습니다'}

    sched = _ensure_scheduler(task)
    current_level = int(sched.get('escalationLevel') or 0)
    next_level = min(current_level + 1, 2)
    target = 'saganwon' if next_level == 1 else 'seungjeongwon'
    target_label = '사간원' if next_level == 1 else '승정원'

    sched['escalationLevel'] = next_level
    sched['lastEscalatedAt'] = now_iso()
    _scheduler_add_flow(task, f'상향: {target_label} 조정: {reason or "작업 정체"}', to=target_label)
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    msg = (
        f'🧭 세자 조정상향 알림\n'
        f'작업 ID: {task_id}\n'
        f'현재 상태: {state}\n'
        f'정체 대응: 개입하여 조정을 진행해 주세요\n'
        f'사유: {reason or "임계시간 초과로 진행 없음"}\n'
        f'⚠️ 보드에 기존 작업이 있으니 중복 생성하지 마세요.'
    )
    wake_agent(target, msg)

    return {'ok': True, 'message': f'{task_id} 상향 완료: {target_label}', 'escalationLevel': next_level}


def handle_scheduler_rollback(task_id, reason=''):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}
    sched = _ensure_scheduler(task)
    snapshot = sched.get('snapshot') or {}
    snap_state = snapshot.get('state')
    if not snap_state:
        return {'ok': False, 'error': f'작업 {task_id} 사용 가능한 롤백 스냅샷이 없습니다'}

    old_state = task.get('state', '')
    task['state'] = snap_state
    task['org'] = snapshot.get('org', task.get('org', ''))
    task['now'] = f'↩️ 세자 조정 자동 롤백: {reason or "이전 안정 지점으로 복구"}'
    task['block'] = '없음'
    sched['retryCount'] = 0
    sched['escalationLevel'] = 0
    sched['stallSince'] = None
    sched['lastProgressAt'] = now_iso()
    _scheduler_add_flow(task, f'롤백 실행: {old_state} → {snap_state}, 사유: {reason or "정체 복구"}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    if snap_state not in _TERMINAL_STATES:
        dispatch_for_state(task_id, task, snap_state, trigger='seja-rollback')

    return {'ok': True, 'message': f'{task_id} 롤백 완료: {snap_state}'}


def handle_scheduler_scan(threshold_sec=600):
    threshold_sec = max(60, int(threshold_sec or 600))
    tasks = load_tasks()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    pending_retries = []
    pending_escalates = []
    pending_rollbacks = []
    actions = []
    changed = False

    for task in tasks:
        task_id = task.get('id', '')
        state = task.get('state', '')
        if not task_id or state in _TERMINAL_STATES or task.get('archived'):
            continue
        if state == 'Blocked':
            continue

        sched = _ensure_scheduler(task)
        task_threshold = int(sched.get('stallThresholdSec') or threshold_sec)
        last_progress = _parse_iso(sched.get('lastProgressAt') or task.get('updatedAt'))
        if not last_progress:
            continue
        stalled_sec = max(0, int((now_dt - last_progress).total_seconds()))
        if stalled_sec < task_threshold:
            continue

        if not sched.get('stallSince'):
            sched['stallSince'] = now_iso()
            changed = True

        retry_count = int(sched.get('retryCount') or 0)
        max_retry = max(0, int(sched.get('maxRetry') or 1))
        level = int(sched.get('escalationLevel') or 0)

        if retry_count < max_retry:
            sched['retryCount'] = retry_count + 1
            sched['lastRetryAt'] = now_iso()
            sched['lastDispatchTrigger'] = 'seja-scan-retry'
            _scheduler_add_flow(task, f'정체 {stalled_sec}초, 자동 재시도 {sched["retryCount"]}회')
            pending_retries.append((task_id, state))
            actions.append({'taskId': task_id, 'action': 'retry', 'stalledSec': stalled_sec})
            changed = True
            continue

        if level < 2:
            next_level = level + 1
            target = 'saganwon' if next_level == 1 else 'seungjeongwon'
            target_label = '사간원' if next_level == 1 else '승정원'
            sched['escalationLevel'] = next_level
            sched['lastEscalatedAt'] = now_iso()
            _scheduler_add_flow(task, f'정체 {stalled_sec}초, 상향 조정 대상: {target_label}', to=target_label)
            pending_escalates.append((task_id, state, target, target_label, stalled_sec))
            actions.append({'taskId': task_id, 'action': 'escalate', 'to': target_label, 'stalledSec': stalled_sec})
            changed = True
            continue

        if sched.get('autoRollback', True):
            rollback_count = int(sched.get('rollbackCount') or 0)
            max_rollback = int(sched.get('maxRollback') or 3)
            snapshot = sched.get('snapshot') or {}
            snap_state = snapshot.get('state')
            if rollback_count >= max_rollback:
                # 최대 롤백 횟수 도달, 무한 루프 방지를 위해 Blocked 로 표시
                if state != 'Blocked':
                    task['state'] = 'Blocked'
                    task['now'] = f'🚫 연속 롤백{rollback_count}회 후에도 진행되지 않아 자동 중단되었습니다'
                    task['block'] = f'연속 정체 및 롤백 {rollback_count}회 실패, 수동 개입 필요'
                    sched['stallSince'] = None
                    _scheduler_add_flow(task, f'연속 롤백 {rollback_count}회, 자동 중단 후 수동 개입 대기')
                    actions.append({'taskId': task_id, 'action': 'blocked', 'reason': f'max rollback {rollback_count}'})
                    changed = True
            elif snap_state and snap_state != state:
                old_state = state
                task['state'] = snap_state
                task['org'] = snapshot.get('org', task.get('org', ''))
                task['now'] = '↩️ 세자 조정 자동 롤백: 안정 지점 복구'
                task['block'] = '없음'
                sched['retryCount'] = 0
                sched['escalationLevel'] = 0
                sched['rollbackCount'] = rollback_count + 1
                sched['stallSince'] = None
                sched['lastProgressAt'] = now_iso()
                _scheduler_add_flow(task, f'연속 정체, 자동 롤백: {old_state} → {snap_state} (제 {rollback_count + 1}회)')
                pending_rollbacks.append((task_id, snap_state))
                actions.append({'taskId': task_id, 'action': 'rollback', 'toState': snap_state})
                changed = True

    if changed:
        save_tasks(tasks)

    for task_id, state in pending_retries:
        retry_task = next((t for t in tasks if t.get('id') == task_id), None)
        if retry_task:
            dispatch_for_state(task_id, retry_task, state, trigger='seja-scan-retry')

    for task_id, state, target, target_label, stalled_sec in pending_escalates:
        msg = (
            f'🧭 세자 조정상향 알림\n'
            f'작업 ID: {task_id}\n'
            f'현재 상태: {state}\n'
            f'정체 시간: {stalled_sec}초\n'
            f'즉시 개입하여 조정을 진행해 주세요\n'
            f'⚠️ 보드에 기존 작업이 있으니 중복 생성하지 마세요.'
        )
        wake_agent(target, msg)

    for task_id, state in pending_rollbacks:
        rollback_task = next((t for t in tasks if t.get('id') == task_id), None)
        if rollback_task and state not in _TERMINAL_STATES:
            dispatch_for_state(task_id, rollback_task, state, trigger='seja-auto-rollback')

    return {
        'ok': True,
        'thresholdSec': threshold_sec,
        'actions': actions,
        'count': len(actions),
        'checkedAt': now_iso(),
    }


def _startup_recover_queued_dispatches():
    """서비스 시작 후 lastDispatchStatus=queued 작업을 스캔하여 재배분.
    해결: kill -9 재시작으로 인해 배분 스레드가 중단되어 작업이 영구적으로 멈추는 문제."""
    tasks = load_tasks()
    recovered = 0
    for task in tasks:
        task_id = task.get('id', '')
        state = task.get('state', '')
        if not task_id or state in _TERMINAL_STATES or task.get('archived'):
            continue
        sched = task.get('_scheduler') or {}
        if sched.get('lastDispatchStatus') == 'queued':
            log.info(f'🔄 시작 복구: {task_id} 상태={state} 이전 배분이 완료되지 않아 재배분합니다')
            sched['lastDispatchTrigger'] = 'startup-recovery'
            dispatch_for_state(task_id, task, state, trigger='startup-recovery')
            recovered += 1
    if recovered:
        log.info(f'✅ 시작 복구 완료: 재배분 {recovered}개 작업')
    else:
        log.info('✅ 시작 시 복구: 복구 대상 없음')


def handle_repair_flow_order():
    """이력 작업의 첫 흐름(임금->홍문관) 오순서를 수정합니다."""
    tasks = load_tasks()
    fixed = 0
    fixed_ids = []

    for task in tasks:
        task_id = task.get('id', '')
        if not task_id.startswith('JJC-'):
            continue
        flow_log = task.get('flow_log') or []
        if not flow_log:
            continue

        first = flow_log[0]
        if first.get('from') != '임금' or first.get('to') != '홍문관':
            continue

        first['to'] = '세자'
        remark = first.get('remark', '')
        if isinstance(remark, str) and (remark.startswith('지시:') or remark.startswith('下旨：')):
            first['remark'] = remark

        if task.get('state') == 'HongmungwanDraft' and task.get('org') == '홍문관' and len(flow_log) == 1:
            task['state'] = 'SejaFinalReview'
            task['org'] = '세자'
            task['now'] = '세자 접수 분류 대기'

        task['updatedAt'] = now_iso()
        fixed += 1
        fixed_ids.append(task_id)

    if fixed:
        save_tasks(tasks)

    return {
        'ok': True,
        'count': fixed,
        'taskIds': fixed_ids[:80],
        'more': max(0, fixed - 80),
        'checkedAt': now_iso(),
    }


def _collect_message_text(msg):
    """메시지 중 검색 가능한 텍스트 수집, task_id/키워드 필터링에 사용."""
    parts = []
    for c in msg.get('content', []) or []:
        ctype = c.get('type')
        if ctype == 'text' and c.get('text'):
            parts.append(str(c.get('text', '')))
        elif ctype == 'thinking' and c.get('thinking'):
            parts.append(str(c.get('thinking', '')))
        elif ctype == 'tool_use':
            parts.append(json.dumps(c.get('input', {}), ensure_ascii=False))
    details = msg.get('details') or {}
    for key in ('output', 'stdout', 'stderr', 'message'):
        val = details.get(key)
        if isinstance(val, str) and val:
            parts.append(val)
    return ''.join(parts)


def _parse_activity_entry(item):
    """session jsonl 의 message 를 칸반 활동 항목으로 통일 파싱."""
    msg = item.get('message') or {}
    role = str(msg.get('role', '')).strip().lower()
    ts = item.get('timestamp', '')

    if role == 'assistant':
        text = ''
        thinking = ''
        tool_calls = []
        for c in msg.get('content', []) or []:
            if c.get('type') == 'text' and c.get('text') and not text:
                text = str(c.get('text', '')).strip()
            elif c.get('type') == 'thinking' and c.get('thinking') and not thinking:
                thinking = str(c.get('thinking', '')).strip()[:200]
            elif c.get('type') == 'tool_use':
                tool_calls.append({
                    'name': c.get('name', ''),
                    'input_preview': json.dumps(c.get('input', {}), ensure_ascii=False)[:100]
                })
        if not (text or thinking or tool_calls):
            return None
        entry = {'at': ts, 'kind': 'assistant'}
        if text:
            entry['text'] = text[:300]
        if thinking:
            entry['thinking'] = thinking
        if tool_calls:
            entry['tools'] = tool_calls
        return entry

    if role in ('toolresult', 'tool_result'):
        details = msg.get('details') or {}
        code = details.get('exitCode')
        if code is None:
            code = details.get('code', details.get('status'))
        output = ''
        for c in msg.get('content', []) or []:
            if c.get('type') == 'text' and c.get('text'):
                output = str(c.get('text', '')).strip()[:200]
                break
        if not output:
            for key in ('output', 'stdout', 'stderr', 'message'):
                val = details.get(key)
                if isinstance(val, str) and val.strip():
                    output = val.strip()[:200]
                    break

        entry = {
            'at': ts,
            'kind': 'tool_result',
            'tool': msg.get('toolName', msg.get('name', '')),
            'exitCode': code,
            'output': output,
        }
        duration_ms = details.get('durationMs')
        if isinstance(duration_ms, (int, float)):
            entry['durationMs'] = int(duration_ms)
        return entry

    if role == 'user':
        text = ''
        for c in msg.get('content', []) or []:
            if c.get('type') == 'text' and c.get('text'):
                text = str(c.get('text', '')).strip()
                break
        if not text:
            return None
        return {'at': ts, 'kind': 'user', 'text': text[:200]}

    return None


def get_agent_activity(agent_id, limit=30, task_id=None):
    """Agent 의 session jsonl 에서 최근 활동 읽기.
    task_id 가 비어있지 않으면 해당 task_id 를 언급한 관련 항목만 반환.
    """
    sessions_dir = OCLAW_HOME / 'agents' / agent_id / 'sessions'
    if not sessions_dir.exists():
        return []

    # 모든 jsonl 스캔 (수정 시간 역순), 최신 우선
    jsonl_files = sorted(sessions_dir.glob('*.jsonl'), key=lambda f: f.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return []

    entries = []
    # task_id 로 필터링하려면 여러 파일 스캔 필요
    files_to_scan = jsonl_files[:3] if task_id else jsonl_files[:1]

    for session_file in files_to_scan:
        try:
            lines = session_file.read_text(errors='ignore').splitlines()
        except Exception:
            continue

        # 시간 순서를 유지하며 정방향 스캔; task_id 가 있으면 해당 task_id 를 언급한 항목 수집
        for ln in lines:
            try:
                item = json.loads(ln)
            except Exception:
                continue
            msg = item.get('message') or {}
            all_text = _collect_message_text(msg)

            # task_id 필터: 해당 task_id 를 언급한 항목만 보존
            if task_id and task_id not in all_text:
                continue
            entry = _parse_activity_entry(item)
            if entry:
                entries.append(entry)

            if len(entries) >= limit:
                break
        if len(entries) >= limit:
            break

    # 마지막 limit 건만 보존
    return entries[-limit:]


def _extract_keywords(title):
    """작업 제목에서 의미 있는 키워드 추출 (session 내용 매칭용)."""
    stop = {'的', '了', '在', '是', '有', '和', '与', '或', '一个', '一篇', '关于', '进行',
            '写', '做', '请', '把', '给', '用', '要', '需要', '面向', '风格', '包含',
            '出', '个', '不', '可以', '应该', '如何', '怎么', '什么', '这个', '那个'}
    # 영문 단어 추출
    en_words = re.findall(r'[a-zA-Z][\w.-]{1,}', title)
    # 2-4자 한자/한글 어구 추출 (더 짧은 단위)
    cn_words = re.findall(r'[\u4e00-\u9fff]{2,4}', title)
    all_words = en_words + cn_words
    kws = [w for w in all_words if w not in stop and len(w) >= 2]
    # 중복 제거 및 순서 보존
    seen = set()
    unique = []
    for w in kws:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique.append(w)
    return unique[:8]  # 최대 8개 키워드


def get_agent_activity_by_keywords(agent_id, keywords, limit=20):
    """agent session 에서 키워드 매칭으로 활동 항목 가져오기.
    키워드를 포함하는 session 파일을 찾아 해당 파일의 활동만 읽음.
    """
    sessions_dir = OCLAW_HOME / 'agents' / agent_id / 'sessions'
    if not sessions_dir.exists():
        return []

    jsonl_files = sorted(sessions_dir.glob('*.jsonl'), key=lambda f: f.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return []

    # 키워드를 포함하는 session 파일 찾기
    target_file = None
    for sf in jsonl_files[:5]:
        try:
            content = sf.read_text(errors='ignore')
        except Exception:
            continue
        hits = sum(1 for kw in keywords if kw.lower() in content.lower())
        if hits >= min(2, len(keywords)):
            target_file = sf
            break

    if not target_file:
        return []

    # session 파일 파싱, user 메시지 단위로 대화 단락 분할
    # 키워드를 포함하는 대화 단락 찾기, 해당 단락의 활동만 반환
    try:
        lines = target_file.read_text(errors='ignore').splitlines()
    except Exception:
        return []

    # 1차: 키워드와 일치하는 user 메시지 위치 찾기
    user_msg_indices = []  # (line_index, user_text)
    for i, ln in enumerate(lines):
        try:
            item = json.loads(ln)
        except Exception:
            continue
        msg = item.get('message') or {}
        if msg.get('role') == 'user':
            text = ''
            for c in msg.get('content', []):
                if c.get('type') == 'text' and c.get('text'):
                    text += c['text']
            user_msg_indices.append((i, text))

    # 키워드와 매칭도가 가장 높은 user 메시지 찾기
    best_idx = -1
    best_hits = 0
    for line_idx, utext in user_msg_indices:
        hits = sum(1 for kw in keywords if kw.lower() in utext.lower())
        if hits > best_hits:
            best_hits = hits
            best_idx = line_idx

    # 대화 단락의 라인 범위 결정: 매칭된 user 메시지부터 다음 user 메시지 이전까지
    if best_idx >= 0 and best_hits >= min(2, len(keywords)):
        # 다음 user 메시지 위치 찾기
        next_user_idx = len(lines)
        for line_idx, _ in user_msg_indices:
            if line_idx > best_idx:
                next_user_idx = line_idx
                break
        start_line = best_idx
        end_line = next_user_idx
    else:
        # 매칭된 대화 단락을 찾지 못함, 빈 값 반환
        return []

    # 2차: 대화 단락 내의 라인만 파싱
    entries = []
    for ln in lines[start_line:end_line]:
        try:
            item = json.loads(ln)
        except Exception:
            continue
        entry = _parse_activity_entry(item)
        if entry:
            entries.append(entry)

    return entries[-limit:]


def get_agent_latest_segment(agent_id, limit=20):
    """Agent 의 가장 최신 대화 단락 가져오기 (마지막 user 메시지부터의 모든 내용).
    활성 작업에 정확한 매칭이 없을 때 Agent 의 실시간 작업 상태 표시용.
    """
    sessions_dir = OCLAW_HOME / 'agents' / agent_id / 'sessions'
    if not sessions_dir.exists():
        return []

    jsonl_files = sorted(sessions_dir.glob('*.jsonl'),
                         key=lambda f: f.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return []

    # 최신 session 파일 읽기
    target_file = jsonl_files[0]
    try:
        lines = target_file.read_text(errors='ignore').splitlines()
    except Exception:
        return []

    # 마지막 user 메시지의 라인 번호 찾기
    last_user_idx = -1
    for i, ln in enumerate(lines):
        try:
            item = json.loads(ln)
        except Exception:
            continue
        msg = item.get('message') or {}
        if msg.get('role') == 'user':
            last_user_idx = i

    if last_user_idx < 0:
        return []

    # 마지막 user 메시지부터 파일 끝까지 파싱
    entries = []
    for ln in lines[last_user_idx:]:
        try:
            item = json.loads(ln)
        except Exception:
            continue
        entry = _parse_activity_entry(item)
        if entry:
            entries.append(entry)

    return entries[-limit:]


def _compute_phase_durations(flow_log):
    """flow_log 에서 각 단계 체류 시간 계산."""
    if not flow_log or len(flow_log) < 1:
        return []
    phases = []
    for i, fl in enumerate(flow_log):
        start_at = fl.get('at', '')
        to_dept = fl.get('to', '')
        remark = fl.get('remark', '')
        # 다음 단계의 시작 시각이 곧 현 단계의 종료 시각
        if i + 1 < len(flow_log):
            end_at = flow_log[i + 1].get('at', '')
            ongoing = False
        else:
            end_at = now_iso()
            ongoing = True
        # 시간 길이 계산
        dur_sec = 0
        try:
            from_dt = datetime.datetime.fromisoformat(start_at.replace('Z', '+00:00'))
            to_dt = datetime.datetime.fromisoformat(end_at.replace('Z', '+00:00'))
            dur_sec = max(0, int((to_dt - from_dt).total_seconds()))
        except Exception:
            pass
        # 사람이 읽을 수 있는 시간 길이
        if dur_sec < 60:
            dur_text = f'{dur_sec}초'
        elif dur_sec < 3600:
            dur_text = f'{dur_sec // 60}분{dur_sec % 60}초'
        elif dur_sec < 86400:
            h, rem = divmod(dur_sec, 3600)
            dur_text = f'{h}시간{rem // 60}분'
        else:
            d, rem = divmod(dur_sec, 86400)
            dur_text = f'{d}일{rem // 3600}시간'
        phases.append({
            'phase': to_dept,
            'from': start_at,
            'to': end_at,
            'durationSec': dur_sec,
            'durationText': dur_text,
            'ongoing': ongoing,
            'remark': remark,
        })
    return phases


def _compute_todos_summary(todos):
    """todos 완료율 집계 계산."""
    if not todos:
        return None
    total = len(todos)
    completed = sum(1 for t in todos if t.get('status') == 'completed')
    in_progress = sum(1 for t in todos if t.get('status') == 'in-progress')
    not_started = total - completed - in_progress
    percent = round(completed / total * 100) if total else 0
    return {
        'total': total,
        'completed': completed,
        'inProgress': in_progress,
        'notStarted': not_started,
        'percent': percent,
    }


def _compute_todos_diff(prev_todos, curr_todos):
    """두 todos 스냅샷 간 차이 계산."""
    prev_map = {str(t.get('id', '')): t for t in (prev_todos or [])}
    curr_map = {str(t.get('id', '')): t for t in (curr_todos or [])}
    changed, added, removed = [], [], []
    for tid, ct in curr_map.items():
        if tid in prev_map:
            pt = prev_map[tid]
            if pt.get('status') != ct.get('status'):
                changed.append({
                    'id': tid, 'title': ct.get('title', ''),
                    'from': pt.get('status', ''), 'to': ct.get('status', ''),
                })
        else:
            added.append({'id': tid, 'title': ct.get('title', '')})
    for tid, pt in prev_map.items():
        if tid not in curr_map:
            removed.append({'id': tid, 'title': pt.get('title', '')})
    if not changed and not added and not removed:
        return None
    return {'changed': changed, 'added': added, 'removed': removed}


def get_task_activity(task_id):
    """작업의 실시간 진척 데이터 가져오기.
    데이터 출처:
    1. 작업 자체의 now / todos / flow_log 필드 (Agent 가 progress 명령으로 능동 보고)
    2. Agent session JSONL 의 대화 로그 (thinking / tool_result / user, 사고 과정 표시용)

    확장 필드:
    - taskMeta: 작업 메타 정보 (title/state/org/output/block/priority/reviewRound/archived)
    - phaseDurations: 각 단계 체류 시간
    - todosSummary: todos 완료율 집계
    - resourceSummary: Agent 리소스 소모 집계 (tokens/cost/elapsed)
    - activity 항목에서 progress/todos 는 state/org 스냅샷 유지
    - activity 의 todos 항목에 diff 필드 포함
    """
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}

    state = task.get('state', '')
    org = task.get('org', '')
    now_text = task.get('now', '')
    todos = task.get('todos', [])
    updated_at = task.get('updatedAt', '')

    # ── 작업 메타 정보 ──
    task_meta = {
        'title': task.get('title', ''),
        'state': state,
        'org': org,
        'output': task.get('output', ''),
        'block': task.get('block', ''),
        'priority': task.get('priority', 'normal'),
        'reviewRound': task.get('review_round', 0),
        'archived': task.get('archived', False),
    }

    # 현재 담당 Agent (기존 로직 호환)
    agent_id = _STATE_AGENT_MAP.get(state)
    if agent_id is None and state in ('InProgress', 'Ready'):
        agent_id = _ORG_AGENT_MAP.get(org)

    # ── 활동 항목 목록 구성 (flow_log + progress_log) ──
    activity = []
    flow_log = task.get('flow_log', [])

    # 1. flow_log 를 활동 항목으로 변환
    for fl in flow_log:
        activity.append({
            'at': fl.get('at', ''),
            'kind': 'flow',
            'from': fl.get('from', ''),
            'to': fl.get('to', ''),
            'remark': fl.get('remark', ''),
        })

    progress_log = task.get('progress_log', [])
    related_agents = set()

    # 리소스 소모 누적
    total_tokens = 0
    total_cost = 0.0
    total_elapsed = 0
    has_resource_data = False

    # todos diff 계산용
    prev_todos_snapshot = None

    if progress_log:
        # 2. 다중 Agent 실시간 진척 로그 (각 progress 마다 자체 todo 스냅샷 보존)
        for pl in progress_log:
            p_at = pl.get('at', '')
            p_agent = pl.get('agent', '')
            p_text = pl.get('text', '')
            p_todos = pl.get('todos', [])
            p_state = pl.get('state', '')
            p_org = pl.get('org', '')
            if p_agent:
                related_agents.add(p_agent)
            # 리소스 소모 누적
            if pl.get('tokens'):
                total_tokens += pl['tokens']
                has_resource_data = True
            if pl.get('cost'):
                total_cost += pl['cost']
                has_resource_data = True
            if pl.get('elapsed'):
                total_elapsed += pl['elapsed']
                has_resource_data = True
            if p_text:
                entry = {
                    'at': p_at,
                    'kind': 'progress',
                    'text': p_text,
                    'agent': p_agent,
                    'agentLabel': pl.get('agentLabel', ''),
                    'state': p_state,
                    'org': p_org,
                }
                # 단일 리소스 데이터
                if pl.get('tokens'):
                    entry['tokens'] = pl['tokens']
                if pl.get('cost'):
                    entry['cost'] = pl['cost']
                if pl.get('elapsed'):
                    entry['elapsed'] = pl['elapsed']
                activity.append(entry)
            if p_todos:
                todos_entry = {
                    'at': p_at,
                    'kind': 'todos',
                    'items': p_todos,
                    'agent': p_agent,
                    'agentLabel': pl.get('agentLabel', ''),
                    'state': p_state,
                    'org': p_org,
                }
                # diff 계산
                diff = _compute_todos_diff(prev_todos_snapshot, p_todos)
                if diff:
                    todos_entry['diff'] = diff
                activity.append(todos_entry)
                prev_todos_snapshot = p_todos

        # 상태로 Agent 를 판단할 수 없을 때만 마지막으로 보고한 Agent 로 폴백
        if not agent_id:
            last_pl = progress_log[-1]
            if last_pl.get('agent'):
                agent_id = last_pl.get('agent')
    else:
        # 기존 데이터 호환: now/todos 만 사용
        if now_text:
            activity.append({
                'at': updated_at,
                'kind': 'progress',
                'text': now_text,
                'agent': agent_id or '',
                'state': state,
                'org': org,
            })
        if todos:
            activity.append({
                'at': updated_at,
                'kind': 'todos',
                'items': todos,
                'agent': agent_id or '',
                'state': state,
                'org': org,
            })

    # 시간순 정렬, 흐름/진척 인터리브가 올바른지 보장
    activity.sort(key=lambda x: x.get('at', ''))

    if agent_id:
        related_agents.add(agent_id)

    # ── Agent Session 활동 병합 (thinking / tool_result / user) ──
    # session JSONL 에서 Agent 의 사고 과정 및 도구 호출 기록 추출
    try:
        session_entries = []
        # 활성 작업: task_id 정확 매칭 시도
        if state not in ('Completed', 'Cancelled'):
            if agent_id:
                entries = get_agent_activity(agent_id, limit=30, task_id=task_id)
                session_entries.extend(entries)
            # 다른 관련 Agent 에서도 가져옴
            for ra in related_agents:
                if ra != agent_id:
                    entries = get_agent_activity(ra, limit=20, task_id=task_id)
                    session_entries.extend(entries)
        else:
            # 완료된 작업: 키워드 기반 매칭
            title = task.get('title', '')
            keywords = _extract_keywords(title)
            if keywords:
                agents_to_scan = list(related_agents) if related_agents else ([agent_id] if agent_id else [])
                for ra in agents_to_scan[:5]:
                    entries = get_agent_activity_by_keywords(ra, keywords, limit=15)
                    session_entries.extend(entries)
        # 중복 제거 (at+kind 로 중복 회피)
        existing_keys = {(a.get('at', ''), a.get('kind', '')) for a in activity}
        for se in session_entries:
            key = (se.get('at', ''), se.get('kind', ''))
            if key not in existing_keys:
                activity.append(se)
                existing_keys.add(key)
        # 재정렬
        activity.sort(key=lambda x: x.get('at', ''))
    except Exception as e:
        log.warning(f'Session JSONL 병합 실패 (task={task_id}): {e}')

    # ── 단계 소요 시간 집계 ──
    phase_durations = _compute_phase_durations(flow_log)

    # ── Todos 집계 ──
    todos_summary = _compute_todos_summary(todos)

    # ── 총 소요 (첫 flow_log 부터 마지막/현재까지) ──
    total_duration = None
    if flow_log:
        try:
            first_at = datetime.datetime.fromisoformat(flow_log[0].get('at', '').replace('Z', '+00:00'))
            if state in ('Completed', 'Cancelled') and len(flow_log) >= 2:
                last_at = datetime.datetime.fromisoformat(flow_log[-1].get('at', '').replace('Z', '+00:00'))
            else:
                last_at = datetime.datetime.now(datetime.timezone.utc)
            dur = max(0, int((last_at - first_at).total_seconds()))
            if dur < 60:
                total_duration = f'{dur}초'
            elif dur < 3600:
                total_duration = f'{dur // 60}분{dur % 60}초'
            elif dur < 86400:
                h, rem = divmod(dur, 3600)
                total_duration = f'{h}시간{rem // 60}분'
            else:
                d, rem = divmod(dur, 86400)
                total_duration = f'{d}일{rem // 3600}시간'
        except Exception:
            pass

    last_active = None
    if updated_at:
        try:
            dt = _parse_iso(updated_at)
            if dt:
                last_active = dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')
            else:
                last_active = updated_at[:19].replace('T', ' ')
        except Exception:
            last_active = updated_at[:19].replace('T', ' ')

    result = {
        'ok': True,
        'taskId': task_id,
        'taskMeta': task_meta,
        'agentId': agent_id,
        'agentLabel': _STATE_LABELS.get(state, state),
        'lastActive': last_active,
        'activity': activity,
        'activitySource': 'progress+session',
        'relatedAgents': sorted(list(related_agents)),
        'phaseDurations': phase_durations,
        'totalDuration': total_duration,
    }
    if todos_summary:
        result['todosSummary'] = todos_summary
    if has_resource_data:
        result['resourceSummary'] = {
            'totalTokens': total_tokens,
            'totalCost': round(total_cost, 4),
            'totalElapsedSec': total_elapsed,
        }
    return result


def get_healthz_payload():
    """헬스체크 응답 본문을 생성한다."""
    task_data_dir = get_task_data_dir()
    checks = {
        'dataDir': task_data_dir.is_dir(),
        'tasksReadable': (task_data_dir / 'tasks_source.json').exists(),
    }
    checks['dataWritable'] = os.access(str(task_data_dir), os.W_OK)
    return {'status': 'ok' if all(checks.values()) else 'degraded', 'ts': now_iso(), 'checks': checks}


# 상태 진행 순서 (수동 진행용)
_STATE_FLOW = {
    'Pending':              ('SejaFinalReview', '임금', '세자', '접수 대기 지시를 세자 검토 단계로 전달'),
    'SejaFinalReview':           ('HongmungwanDraft', '세자', '홍문관', '세자 검토 완료, 홍문관 기안으로 이동'),
    'HongmungwanDraft':     ('SaganwonFinalReview', '홍문관', '사간원', '홍문관 기안안을 사간원 심의로 전달'),
    'SaganwonFinalReview':       ('SeungjeongwonAssigned', '사간원', '승정원', '사간원 승인 후 승정원 배분으로 이동'),
    'SeungjeongwonAssigned':('InProgress', '승정원', '육조', '승정원 배분 완료, 육조 집행 시작'),
    'Ready':                ('InProgress', '승정원', '육조', '집행 대기 상태에서 집행 시작'),
    'InProgress':           ('FinalReview', '육조', '승정원', '육조 집행 완료, 승정원 취합 검토로 이동'),
    'FinalReview':          ('Completed', '승정원', '세자', '취합 검토 완료, 세자 결과 보고 후 종료'),
}
_STATE_LABELS = {
    'Pending': '접수 대기',
    'SejaFinalReview': '세자 검토',
    'HongmungwanDraft': '홍문관 기안',
    'SaganwonFinalReview': '사간원 심의',
    'SeungjeongwonAssigned': '승정원 배분 완료',
    'Ready': '집행 대기',
    'InProgress': '집행 중',
    'FinalReview': '취합 검토',
    'Completed': '완료',
    'Blocked': '중단',
    'Cancelled': '취소',
    'PendingConfirm': '확인 대기',
}


def dispatch_for_state(task_id, task, new_state, trigger='state-transition'):
    """진행/심의 이후 해당 Agent 자동 배분 (백그라운드 비동기, 응답 블로킹 없음)."""
    agent_id = _STATE_AGENT_MAP.get(new_state)
    if agent_id is None and new_state in ('InProgress', 'Next'):
        org = task.get('org', '')
        agent_id = _ORG_AGENT_MAP.get(org)
    if not agent_id:
        log.info(f'ℹ️ {task_id} 새 상태 {new_state}에 대응 Agent가 없어 자동 배분을 건너뜁니다')
        return

    _update_task_scheduler(task_id, lambda t, s: (
        s.update({
            'lastDispatchAt': now_iso(),
            'lastDispatchStatus': 'queued',
            'lastDispatchAgent': agent_id,
            'lastDispatchTrigger': trigger,
        }),
        _scheduler_add_flow(t, f'배분 대기열 등록: {new_state} → {agent_id} ({trigger})', to=_STATE_LABELS.get(new_state, new_state))
    ))

    title = task.get('title', '(제목 없음)')
    target_dept = task.get('targetDept', '')

    # agent_id 에 따라 맞춤 메시지 구성
    _msgs = {
        'seja': (
            f'📜 임금 지시 처리 요청\n'
            f'작업 ID: {task_id}\n'
            f'지시: {title}\n'
            f'⚠️ 대시보드에 이미 같은 작업이 있습니다. 새 작업 생성 대신 kanban_update.py 로 상태를 갱신하세요.\n'
            f'홍문관 기안 단계로 즉시 전달하세요.'
        ),
        'hongmungwan': (
            f'📜 홍문관 기안 요청\n'
            f'작업 ID: {task_id}\n'
            f'지시: {title}\n'
            f'⚠️ 대시보드에 이미 같은 작업이 있습니다. 새 작업 생성 대신 kanban_update.py 로 상태를 갱신하세요.\n'
            f'홍문관 기안 -> 사간원 심의 -> 승정원 배분 -> 육조 집행 흐름으로 진행하세요.'
        ),
        'saganwon': (
            f'📋 사간원 심의 요청\n'
            f'작업 ID: {task_id}\n'
            f'지시: {title}\n'
            f'⚠️ 대시보드에 이미 같은 작업이 있습니다. 새 작업 생성 대신 상태를 갱신하세요.\n'
            f'홍문관 기안안을 검토하고 승인 또는 반려 의견을 남기세요.'
        ),
        'seungjeongwon': (
            f'📮 승정원 배분 요청\n'
            f'작업 ID: {task_id}\n'
            f'지시: {title}\n'
            f'{"권장 집행 부서: " + target_dept if target_dept else ""}\n'
            f'⚠️ 대시보드에 이미 같은 작업이 있습니다. 새 작업 생성 대신 상태를 갱신하세요.\n'
            f'기안안을 분석해 육조 집행으로 배분하세요.'
        ),
    }
    msg = _msgs.get(agent_id, (
        f'📌 작업 처리 요청\n'
        f'작업 ID: {task_id}\n'
        f'지시: {title}\n'
        f'⚠️ 대시보드에 이미 같은 작업이 있습니다. 새 작업 생성 대신 kanban_update.py 로 상태를 갱신하세요.'
    ))

    def _do_dispatch():
        try:
            # Gateway 가 일시적으로 도달 불가할 수 있음 (슬립 복귀, 프로세스 재시작), 대기 후 재시도
            import time as _time
            _gw_alive = False
            for _gw_attempt in range(3):
                if _check_gateway_alive():
                    _gw_alive = True
                    break
                if _gw_attempt < 2:
                    _time.sleep(5 * (_gw_attempt + 1))  # 5s, 10s
            if not _gw_alive:
                log.warning(f'⚠️ {task_id} 자동 배분 건너뜀: Gateway 미실행(3회 재시도 실패)')
                _update_task_scheduler(task_id, lambda t, s: s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'gateway-offline',
                    'lastDispatchAgent': agent_id,
                    'lastDispatchTrigger': trigger,
                }))
                return
            # Fix #139/#182: dispatch channel 설정 가능; 미설정 시 --deliver 미전달로
            # "unknown channel: feishu" 오류 회피 (피슈 미사용자)
            _agent_cfg = read_json(DATA / 'agent_config.json', {})
            _channel = (_agent_cfg.get('dispatchChannel') or '').strip()
            openclaw_bin = _resolve_openclaw_bin()
            if not openclaw_bin:
                err = 'OpenClaw CLI를 찾을 수 없습니다. openclaw 설치/ PATH 등록을 확인하세요. Windows는 OPENCLAW_BIN에 openclaw.cmd를 지정할 수 있습니다'
                log.warning(f'⚠️ {task_id} 자동 배분 예외: {err}')
                _update_task_scheduler(task_id, lambda t, s: (
                    s.update({
                        'lastDispatchAt': now_iso(),
                        'lastDispatchStatus': 'openclaw-missing',
                        'lastDispatchAgent': agent_id,
                        'lastDispatchTrigger': trigger,
                        'lastDispatchError': err,
                    }),
                    _scheduler_add_flow(t, f'배분 예외: OpenClaw CLI를 찾을 수 없음 ({trigger})', to=t.get('org', ''))
                ))
                return
            cmd = [openclaw_bin, 'agent', '--agent', agent_id, '-m', msg, '--timeout', '300']
            if _channel:
                cmd.extend(['--deliver', '--channel', _channel])
            max_retries = 2
            err = ''
            for attempt in range(1, max_retries + 1):
                log.info(f'🔄 자동 배분 {task_id} → {agent_id} ({attempt}회차)...')
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=310)
                if result.returncode == 0:
                    log.info(f'✅ {task_id} 자동 배분 성공 → {agent_id}')
                    _update_task_scheduler(task_id, lambda t, s: (
                        s.update({
                            'lastDispatchAt': now_iso(),
                            'lastDispatchStatus': 'success',
                            'lastDispatchAgent': agent_id,
                            'lastDispatchTrigger': trigger,
                            'lastDispatchError': '',
                        }),
                        _scheduler_add_flow(t, f'배분 성공: {agent_id} ({trigger})', to=t.get('org', ''))
                    ))
                    return
                err = result.stderr[:200] if result.stderr else result.stdout[:200]
                log.warning(f'⚠️ {task_id} 자동 배분 실패({attempt}회차): {err}')
                if attempt < max_retries:
                    import time
                    time.sleep(5)
            log.error(f'❌ {task_id} 자동 배분 최종 실패 → {agent_id}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'failed',
                    'lastDispatchAgent': agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': err,
                }),
                _scheduler_add_flow(t, f'배분 실패: {agent_id} ({trigger})', to=t.get('org', ''))
            ))
        except subprocess.TimeoutExpired:
            log.error(f'❌ {task_id} 자동 배분 시간 초과 → {agent_id}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'timeout',
                    'lastDispatchAgent': agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': 'timeout',
                }),
                _scheduler_add_flow(t, f'배분 시간 초과: {agent_id} ({trigger})', to=t.get('org', ''))
            ))
        except FileNotFoundError as e:
            err = f'OpenClaw CLI를 찾을 수 없음: {e}'
            log.warning(f'⚠️ {task_id} 자동 배분 예외: {err}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'openclaw-missing',
                    'lastDispatchAgent': agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': err[:200],
                }),
                _scheduler_add_flow(t, f'배분 예외: OpenClaw CLI를 찾을 수 없음 ({trigger})', to=t.get('org', ''))
            ))
        except Exception as e:
            log.warning(f'⚠️ {task_id} 자동 배분 예외: {e}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'error',
                    'lastDispatchAgent': agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': str(e)[:200],
                }),
                _scheduler_add_flow(t, f'배분 예외: {agent_id} ({trigger})', to=t.get('org', ''))
            ))

    threading.Thread(target=_do_dispatch, daemon=True).start()
    log.info(f'🚀 {task_id} 단계 전진 후 자동 배분 → {agent_id}')


def handle_advance_state(task_id, comment=''):
    """작업을 다음 단계로 수동 진행 (정체 해소용), 진행 후 해당 Agent 자동 배분."""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'작업 {task_id}이(가) 존재하지 않습니다'}
    cur = task.get('state', '')
    if cur not in _STATE_FLOW:
        return {'ok': False, 'error': f'작업 {task_id} 상태가 {cur}이어서 전진할 수 없습니다'}
    _ensure_scheduler(task)
    _scheduler_snapshot(task, f'advance-before-{cur}')
    next_state, from_dept, to_dept, default_remark = _STATE_FLOW[cur]
    remark = comment or default_remark

    task['state'] = next_state
    task['now'] = f'⬇️ 수동 전진: {remark}'
    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': from_dept,
        'to': to_dept,
        'remark': f'⬇️ 수동 전진: {remark}'
    })
    _scheduler_mark_progress(task, f'수동 전진 {cur} -> {next_state}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    # 🚀 진행 후 해당 Agent 자동 배분 (Completed 상태는 배분 불필요)
    if next_state != 'Completed':
        dispatch_for_state(task_id, task, next_state)

    from_label = _STATE_LABELS.get(cur, cur)
    to_label = _STATE_LABELS.get(next_state, next_state)
    dispatched = ' (Agent 자동 배분 완료)' if next_state != 'Completed' else ''
    return {'ok': True, 'message': f'{task_id} {from_label} → {to_label}{dispatched}'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # 4xx/5xx 오류 요청만 기록
        if args and len(args) >= 1:
            status = str(args[0]) if args else ''
            if status.startswith('4') or status.startswith('5'):
                log.warning(f'{self.client_address[0]} {fmt % args}')

    def handle_error(self):
        pass  # 연결 오류 묵음 처리, BrokenPipe 충돌 방지

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass  # 클라이언트 연결 끊김, 무시

    def do_OPTIONS(self):
        self.send_response(200)
        cors_headers(self)
        self.end_headers()

    def send_json(self, data, code=200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            cors_headers(self)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_file(self, path: pathlib.Path, mime='text/html; charset=utf-8'):
        if not path.exists():
            self.send_error(404)
            return
        try:
            body = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            cors_headers(self)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, rel_path):
        """dist/ 디렉터리의 정적 파일을 제공합니다."""
        safe = rel_path.replace('\\', '/').lstrip('/')
        if '..' in safe:
            self.send_error(403)
            return True
        fp = DIST / safe
        if fp.is_file():
            mime = _MIME_TYPES.get(fp.suffix.lower(), 'application/octet-stream')
            self.send_file(fp, mime)
            return True
        return False

    def _check_auth(self):
        """인증을 확인하고 실패 시 True를 반환합니다(401 응답 전송 완료)."""
        p = urlparse(self.path).path.rstrip('/')
        if not requires_auth(p):
            return False
        token = extract_token(self.headers)
        if not token or not verify_token(token):
            self.send_json({'ok': False, 'error': '로그인이 필요하거나 세션이 만료되었습니다'}, 401)
            return True
        return False

    def do_GET(self):
        p = urlparse(self.path).path.rstrip('/')
        # 인증 상태 엔드포인트(공개)
        if p == '/api/auth/status':
            self.send_json({'enabled': auth_enabled(), 'configured': auth_configured()})
            return
        if self._check_auth():
            return
        if p in ('', '/dashboard', '/dashboard.html'):
            self.send_file(DIST / 'index.html')
        elif p == '/healthz':
            self.send_json(get_healthz_payload())
        elif p == '/api/live-status':
            task_data_dir = get_task_data_dir()
            self.send_json(read_json(task_data_dir / 'live_status.json'))
        elif p == '/api/agent-config':
            self.send_json(read_json(DATA / 'agent_config.json'))
        elif p == '/api/model-change-log':
            self.send_json(read_json(DATA / 'model_change_log.json', []))
        elif p == '/api/last-result':
            self.send_json(read_json(DATA / 'last_model_change_result.json', {}))
        elif p == '/api/officials-stats':
            self.send_json(read_json(DATA / 'officials_stats.json', {}))
        elif p == '/api/morning-brief':
            self.send_json(read_json(DATA / 'morning_brief.json', {}))
        elif p == '/api/morning-config':
            migrate_notification_config()
            self.send_json(read_json(DATA / 'morning_brief_config.json', {
                'categories': [
                    {'name': '정치', 'enabled': True},
                    {'name': '군사', 'enabled': True},
                    {'name': '경제', 'enabled': True},
                    {'name': 'AI 대형모델', 'enabled': True},
                ],
                'keywords': [], 'custom_feeds': [],
                'notification': {'enabled': True, 'channel': 'feishu', 'webhook': ''},
            }))
        elif p == '/api/notification-channels':
            self.send_json({'ok': True, 'channels': get_channel_info()})
        elif p.startswith('/api/morning-brief/'):
            date = p.split('/')[-1]
            # 날짜 형식을 YYYYMMDD로 표준화(YYYY-MM-DD 입력 호환)
            date_clean = date.replace('-', '')
            if not date_clean.isdigit() or len(date_clean) != 8:
                self.send_json({'ok': False, 'error': f'날짜 형식이 올바르지 않습니다: {date}. YYYYMMDD를 사용해 주세요'}, 400)
                return
            self.send_json(read_json(DATA / f'morning_brief_{date_clean}.json', {}))
        elif p == '/api/remote-skills-list':
            self.send_json(get_remote_skills_list())
        elif p.startswith('/api/skill-content/'):
            # /api/skill-content/{agentId}/{skillName}
            parts = p.replace('/api/skill-content/', '').split('/', 1)
            if len(parts) == 2:
                self.send_json(read_skill_content(parts[0], parts[1]))
            else:
                self.send_json({'ok': False, 'error': 'Usage: /api/skill-content/{agentId}/{skillName}'}, 400)
        elif p.startswith('/api/task-activity/'):
            task_id = p.replace('/api/task-activity/', '')
            if not task_id:
                self.send_json({'ok': False, 'error': 'task_id required'}, 400)
            else:
                self.send_json(get_task_activity(task_id))
        elif p.startswith('/api/scheduler-state/'):
            task_id = p.replace('/api/scheduler-state/', '')
            if not task_id:
                self.send_json({'ok': False, 'error': 'task_id required'}, 400)
            else:
                self.send_json(get_scheduler_state(task_id))
        elif p == '/api/agents-status':
            self.send_json(get_agents_status())
        elif p.startswith('/api/task-output/'):
            task_id = p.replace('/api/task-output/', '')
            if not task_id or not _SAFE_NAME_RE.match(task_id):
                self.send_json({'ok': False, 'error': 'invalid task_id'}, 400)
            else:
                tasks = load_tasks()
                task = next((t for t in tasks if t.get('id') == task_id), None)
                if not task:
                    self.send_json({'ok': False, 'error': 'task not found'}, 404)
                else:
                    output_path = task.get('output', '')
                    if not output_path or output_path == '-':
                        self.send_json({'ok': True, 'taskId': task_id, 'content': '', 'exists': False})
                    else:
                        p_out = pathlib.Path(output_path)
                        if not p_out.exists():
                            self.send_json({'ok': True, 'taskId': task_id, 'content': '', 'exists': False})
                        else:
                            try:
                                content = p_out.read_text(encoding='utf-8', errors='replace')[:50000]
                                self.send_json({'ok': True, 'taskId': task_id, 'content': content, 'exists': True})
                            except Exception as e:
                                self.send_json({'ok': False, 'error': f'읽기에 실패했습니다: {e}'}, 500)
        elif p.startswith('/api/agent-activity/'):
            agent_id = p.replace('/api/agent-activity/', '')
            if not agent_id or not _SAFE_NAME_RE.match(agent_id):
                self.send_json({'ok': False, 'error': 'invalid agent_id'}, 400)
            else:
                self.send_json({'ok': True, 'agentId': agent_id, 'activity': get_agent_activity(agent_id)})
        # ── 조정 토의 ──
        elif p == '/api/court-discuss/list':
            self.send_json({'ok': True, 'sessions': cd_list()})
        elif p == '/api/court-discuss/officials':
            self.send_json({'ok': True, 'officials': CD_PROFILES})
        elif p.startswith('/api/court-discuss/session/'):
            sid = p.replace('/api/court-discuss/session/', '')
            data = cd_get(sid)
            self.send_json(data if data else {'ok': False, 'error': 'session not found'}, 200 if data else 404)
        elif p == '/api/court-discuss/fate':
            self.send_json({'ok': True, 'event': cd_fate()})
        elif self._serve_static(p):
            pass  # _serve_static에서 처리됨(JS/CSS/이미지 등)
        else:
            # SPA fallback: /api/가 아니면 index.html 반환
            if not p.startswith('/api/'):
                idx = DIST / 'index.html'
                if idx.exists():
                    self.send_file(idx)
                    return
            self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path).path.rstrip('/')
        length = int(self.headers.get('Content-Length', 0))
        if length > MAX_REQUEST_BODY:
            self.send_json({'ok': False, 'error': f'Request body too large (max {MAX_REQUEST_BODY} bytes)'}, 413)
            return
        raw = self.rfile.read(length) if length else b''
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            self.send_json({'ok': False, 'error': 'invalid JSON'}, 400)
            return

        # ── 인증 엔드포인트(공개) ──
        if p == '/api/auth/setup':
            pw = body.get('password', '')
            if not isinstance(pw, str) or not pw:
                self.send_json({'ok': False, 'error': '비밀번호를 입력해 주세요'}, 400)
                return
            self.send_json(setup_password(pw))
            return
        if p == '/api/auth/login':
            pw = body.get('password', '')
            if not isinstance(pw, str) or not pw:
                self.send_json({'ok': False, 'error': '비밀번호를 입력해 주세요'}, 400)
                return
            if verify_password(pw):
                token = create_token()
                resp = {'ok': True, 'token': token}
                # HttpOnly 쿠키도 함께 설정
                try:
                    body_bytes = json.dumps(resp, ensure_ascii=False).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(body_bytes)))
                    self.send_header('Set-Cookie', f'edict_token={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400')
                    cors_headers(self)
                    self.end_headers()
                    self.wfile.write(body_bytes)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_json({'ok': False, 'error': '비밀번호가 올바르지 않습니다'}, 401)
            return

        # ── 인증 검사 ──
        if self._check_auth():
            return

        if p == '/api/morning-config':
            if not isinstance(body, dict):
                self.send_json({'ok': False, 'error': '요청 본문은 JSON 객체여야 합니다'}, 400)
                return
            allowed_keys = {'categories', 'keywords', 'custom_feeds', 'notification', 'feishu_webhook'}
            unknown = set(body.keys()) - allowed_keys
            if unknown:
                self.send_json({'ok': False, 'error': f'알 수 없는 필드: {", ".join(unknown)}'}, 400)
                return
            if 'categories' in body and not isinstance(body['categories'], list):
                self.send_json({'ok': False, 'error': 'categories는 배열이어야 합니다'}, 400)
                return
            if 'keywords' in body and not isinstance(body['keywords'], list):
                self.send_json({'ok': False, 'error': 'keywords는 배열이어야 합니다'}, 400)
                return
            if 'notification' in body:
                noti = body['notification']
                if not isinstance(noti, dict):
                    self.send_json({'ok': False, 'error': 'notification은 객체여야 합니다'}, 400)
                    return
                channel_type = noti.get('channel', 'feishu')
                if channel_type not in NOTIFICATION_CHANNELS:
                    self.send_json({'ok': False, 'error': f'지원하지 않는 채널입니다: {channel_type}'}, 400)
                    return
                webhook = noti.get('webhook', '').strip()
                if webhook:
                    channel_cls = get_channel(channel_type)
                    if channel_cls and not channel_cls.validate_webhook(webhook):
                        self.send_json({'ok': False, 'error': f'{channel_cls.label} Webhook URL이 올바르지 않습니다'}, 400)
                        return
            webhook_legacy = body.get('feishu_webhook', '').strip()
            if webhook_legacy and 'notification' not in body:
                body['notification'] = {'enabled': True, 'channel': 'feishu', 'webhook': webhook_legacy}
            cfg_path = DATA / 'morning_brief_config.json'
            cfg_path.write_text(json.dumps(body, ensure_ascii=False, indent=2))
            self.send_json({'ok': True, 'message': '구독 설정을 저장했습니다'})
            return

        if p == '/api/scheduler-scan':
            threshold_sec = body.get('thresholdSec', 180)
            try:
                result = handle_scheduler_scan(threshold_sec)
                self.send_json(result)
            except Exception as e:
                self.send_json({'ok': False, 'error': f'scheduler scan failed: {e}'}, 500)
            return

        if p == '/api/repair-flow-order':
            try:
                self.send_json(handle_repair_flow_order())
            except Exception as e:
                self.send_json({'ok': False, 'error': f'repair flow order failed: {e}'}, 500)
            return

        if p == '/api/scheduler-retry':
            task_id = body.get('taskId', '').strip()
            reason = body.get('reason', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            self.send_json(handle_scheduler_retry(task_id, reason))
            return

        if p == '/api/scheduler-escalate':
            task_id = body.get('taskId', '').strip()
            reason = body.get('reason', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            self.send_json(handle_scheduler_escalate(task_id, reason))
            return

        if p == '/api/scheduler-rollback':
            task_id = body.get('taskId', '').strip()
            reason = body.get('reason', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            self.send_json(handle_scheduler_rollback(task_id, reason))
            return

        if p == '/api/morning-brief/refresh':
            force = body.get('force', True)  # 대시보드 수동 실행 시 기본 강제 갱신
            def do_refresh():
                try:
                    cmd = ['python3', str(SCRIPTS / 'fetch_morning_news.py')]
                    if force:
                        cmd.append('--force')
                    subprocess.run(cmd, timeout=120)
                    push_to_feishu()
                except Exception as e:
                    print(f'[refresh error] {e}', file=sys.stderr)
            threading.Thread(target=do_refresh, daemon=True).start()
            self.send_json({'ok': True, 'message': '수집을 시작했습니다. 약 30~60초 후 새로고침해 주세요'})
            return

        if p == '/api/add-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', body.get('name', '')).strip()
            desc = body.get('description', '').strip() or skill_name
            trigger = body.get('trigger', '').strip()
            if not agent_id or not skill_name:
                self.send_json({'ok': False, 'error': 'agentId and skillName required'}, 400)
                return
            result = add_skill_to_agent(agent_id, skill_name, desc, trigger)
            self.send_json(result)
            return

        if p == '/api/add-remote-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', '').strip()
            source_url = body.get('sourceUrl', '').strip()
            description = body.get('description', '').strip()
            if not agent_id or not skill_name or not source_url:
                self.send_json({'ok': False, 'error': 'agentId, skillName, and sourceUrl required'}, 400)
                return
            result = add_remote_skill(agent_id, skill_name, source_url, description)
            self.send_json(result)
            return

        if p == '/api/remote-skills-list':
            result = get_remote_skills_list()
            self.send_json(result)
            return

        if p == '/api/update-remote-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', '').strip()
            if not agent_id or not skill_name:
                self.send_json({'ok': False, 'error': 'agentId and skillName required'}, 400)
                return
            result = update_remote_skill(agent_id, skill_name)
            self.send_json(result)
            return

        if p == '/api/remove-remote-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', '').strip()
            if not agent_id or not skill_name:
                self.send_json({'ok': False, 'error': 'agentId and skillName required'}, 400)
                return
            result = remove_remote_skill(agent_id, skill_name)
            self.send_json(result)
            return

        if p == '/api/task-action':
            task_id = body.get('taskId', '').strip()
            action = body.get('action', '').strip()  # stop, cancel, resume
            reason = body.get('reason', '').strip() or f'임금이 대시보드에서 {action} 실행'
            if not task_id or action not in ('stop', 'cancel', 'resume'):
                self.send_json({'ok': False, 'error': 'taskId and action(stop/cancel/resume) required'}, 400)
                return
            result = handle_task_action(task_id, action, reason)
            self.send_json(result)
            return

        if p == '/api/archive-task':
            task_id = body.get('taskId', '').strip() if body.get('taskId') else ''
            archived = body.get('archived', True)
            archive_all = body.get('archiveAllDone', False)
            if not task_id and not archive_all:
                self.send_json({'ok': False, 'error': 'taskId or archiveAllDone required'}, 400)
                return
            result = handle_archive_task(task_id, archived, archive_all)
            self.send_json(result)
            return

        if p == '/api/task-todos':
            task_id = body.get('taskId', '').strip()
            todos = body.get('todos', [])  # [{id, title, status}]
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            # todos 입력 검증
            if not isinstance(todos, list) or len(todos) > 200:
                self.send_json({'ok': False, 'error': 'todos must be a list (max 200 items)'}, 400)
                return
            valid_statuses = {'not-started', 'in-progress', 'completed'}
            for td in todos:
                if not isinstance(td, dict) or 'id' not in td or 'title' not in td:
                    self.send_json({'ok': False, 'error': 'each todo must have id and title'}, 400)
                    return
                if td.get('status', 'not-started') not in valid_statuses:
                    td['status'] = 'not-started'
            result = update_task_todos(task_id, todos)
            self.send_json(result)
            return

        if p == '/api/create-task':
            title = body.get('title', '').strip()
            org = body.get('org', '홍문관').strip()
            official = body.get('official', '홍문관 대제학').strip()
            priority = body.get('priority', 'normal').strip()
            template_id = body.get('templateId', '')
            params = body.get('params', {})
            if not title:
                self.send_json({'ok': False, 'error': 'title required'}, 400)
                return
            target_dept = body.get('targetDept', '').strip()
            result = handle_create_task(title, org, official, priority, template_id, params, target_dept)
            self.send_json(result)
            return

        if p == '/api/review-action':
            task_id = body.get('taskId', '').strip()
            action = body.get('action', '').strip()  # approve, reject
            comment = body.get('comment', '').strip()
            if not task_id or action not in ('approve', 'reject'):
                self.send_json({'ok': False, 'error': 'taskId and action(approve/reject) required'}, 400)
                return
            result = handle_review_action(task_id, action, comment)
            self.send_json(result)
            return

        if p == '/api/advance-state':
            task_id = body.get('taskId', '').strip()
            comment = body.get('comment', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            result = handle_advance_state(task_id, comment)
            self.send_json(result)
            return

        if p == '/api/agent-wake':
            agent_id = body.get('agentId', '').strip()
            message = body.get('message', '').strip()
            if not agent_id:
                self.send_json({'ok': False, 'error': 'agentId required'}, 400)
                return
            result = wake_agent(agent_id, message)
            self.send_json(result)
            return

        if p == '/api/set-model':
            agent_id = body.get('agentId', '').strip()
            model = body.get('model', '').strip()
            if not agent_id or not model:
                self.send_json({'ok': False, 'error': 'agentId and model required'}, 400)
                return

            # Write to pending (atomic)
            pending_path = DATA / 'pending_model_changes.json'
            def update_pending(current):
                current = [x for x in current if x.get('agentId') != agent_id]
                current.append({'agentId': agent_id, 'model': model})
                return current
            atomic_json_update(pending_path, update_pending, [])

            # Async apply
            def apply_async():
                try:
                    subprocess.run(['python3', str(SCRIPTS / 'apply_model_changes.py')], timeout=30)
                    subprocess.run(['python3', str(SCRIPTS / 'sync_agent_config.py')], timeout=10)
                except Exception as e:
                    print(f'[apply error] {e}', file=sys.stderr)

            threading.Thread(target=apply_async, daemon=True).start()
            self.send_json({'ok': True, 'message': f'Queued: {agent_id} → {model}'})

        # Fix #139: 배분 채널 설정(feishu/telegram/wecom/signal/tui)
        elif p == '/api/set-dispatch-channel':
            channel = body.get('channel', '').strip()
            allowed = {'feishu', 'telegram', 'wecom', 'signal', 'tui', 'discord', 'slack'}
            if not channel or channel not in allowed:
                self.send_json({'ok': False, 'error': f'channel must be one of: {", ".join(sorted(allowed))}'}, 400)
                return
            def _set_channel(cfg):
                cfg['dispatchChannel'] = channel
                return cfg
            atomic_json_update(DATA / 'agent_config.json', _set_channel, {})
            self.send_json({'ok': True, 'message': f'배분 채널을 {channel}(으)로 변경했습니다'})

        # ── 조정 토의 POST ──
        elif p == '/api/court-discuss/start':
            topic = body.get('topic', '').strip()
            officials = body.get('officials', [])
            task_id = body.get('taskId', '').strip()
            if not topic:
                self.send_json({'ok': False, 'error': 'topic required'}, 400)
                return
            if not officials or not isinstance(officials, list):
                self.send_json({'ok': False, 'error': 'officials list required'}, 400)
                return
            # 관원 ID 검증
            valid_ids = set(CD_PROFILES.keys())
            officials = [o for o in officials if o in valid_ids]
            if len(officials) < 2:
                self.send_json({'ok': False, 'error': '관원을 최소 2명 이상 선택해 주세요'}, 400)
                return
            self.send_json(cd_create(topic, officials, task_id))

        elif p == '/api/court-discuss/advance':
            sid = body.get('sessionId', '').strip()
            user_msg = body.get('userMessage', '').strip() or None
            decree = body.get('decree', '').strip() or None
            if not sid:
                self.send_json({'ok': False, 'error': 'sessionId required'}, 400)
                return
            self.send_json(cd_advance(sid, user_msg, decree))

        elif p == '/api/court-discuss/conclude':
            sid = body.get('sessionId', '').strip()
            if not sid:
                self.send_json({'ok': False, 'error': 'sessionId required'}, 400)
                return
            self.send_json(cd_conclude(sid))

        elif p == '/api/court-discuss/destroy':
            sid = body.get('sessionId', '').strip()
            if sid:
                cd_destroy(sid)
            self.send_json({'ok': True})

        else:
            self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description='3사6조 대시보드 서버')
    parser.add_argument('--port', type=int, default=7891)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--cors', default=None, help='Allowed CORS origin (default: reflect request Origin header)')
    args = parser.parse_args()

    global ALLOWED_ORIGIN, _DASHBOARD_PORT, _DEFAULT_ORIGINS
    ALLOWED_ORIGIN = args.cors
    _DASHBOARD_PORT = args.port
    _DEFAULT_ORIGINS = _DEFAULT_ORIGINS | {
        f'http://127.0.0.1:{args.port}', f'http://localhost:{args.port}',
    }

    server = HTTPServer((args.host, args.port), Handler)
    log.info(f'3사6조 대시보드 시작 → http://{args.host}:{args.port}')
    print('   Ctrl+C로 종료')

    auth_init(DATA)
    if auth_enabled():
        log.info('🔒 JWT 인증 활성화')
    else:
        log.info('🔓 인증 미설정: 모든 API 공개 상태 (POST /api/auth/setup으로 비밀번호 설정)')

    migrate_notification_config()

    # 시작 복구: 이전에 중단된 queued 작업 재배분
    threading.Timer(3.0, _startup_recover_queued_dispatches).start()

    # 정기 점검: 120초마다 정체 작업을 스캔하여 재시도/승격/롤백
    def _periodic_scheduler_scan():
        while True:
            try:
                import time as _time
                _time.sleep(120)
                result = handle_scheduler_scan(threshold_sec=180)
                count = result.get('count', 0) if isinstance(result, dict) else 0
                if count > 0:
                    log.info(f'🔍 정기 점검: {count}개 조치')
            except Exception as e:
                log.warning(f'정기 점검 예외: {e}')
    threading.Thread(target=_periodic_scheduler_scan, daemon=True).start()
    log.info('🔍 정기 점검 시작(120초 주기)')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n중지되었습니다')


if __name__ == '__main__':
    main()
