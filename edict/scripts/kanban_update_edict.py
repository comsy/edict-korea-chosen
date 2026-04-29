#!/usr/bin/env python3
"""
칸반 업무 갱신 도구 - Edict 호환 계층

구버전과 100% 동일한 CLI 인터페이스를 유지하면서, 내부적으로 Edict REST API를 호출합니다.
API를 사용할 수 없는 경우 JSON 파일에 폴백하여 기록합니다(전환기 보장).

사용법(구버전과 100% 호환):
  python3 kanban_update.py create JJC-20260223-012 "업무 제목" hongmungwan 홍문관 홍문학사
  python3 kanban_update.py state JJC-20260223-012 saganwon "기획안이 사간원에 제출됨"
  python3 kanban_update.py flow JJC-20260223-012 "홍문관" "사간원" "기획안 심의 제출"
  python3 kanban_update.py done JJC-20260223-012 "/path/to/output" "업무 완료 요약"
  python3 kanban_update.py todo JJC-20260223-012 1 "API 인터페이스 구현" in-progress
  python3 kanban_update.py progress JJC-20260223-012 "요구사항 분석 중" "1.조사✅|2.문서🔄|3.프로토타입"
"""

import json
import logging
import os
import re
import sys
import pathlib

log = logging.getLogger('kanban')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

# Edict API 주소 — 환경변수 > 기본값 localhost:8000
EDICT_API_URL = os.environ.get('EDICT_API_URL', 'http://localhost:8000')

# API 모드 설정 (EDICT_MODE=api | json | auto)
EDICT_MODE = os.environ.get('EDICT_MODE', 'auto').lower()

# ── 텍스트 정제 로직 (구버전과 완전 동일) ──

_MIN_TITLE_LEN = 6
_JUNK_TITLES = {
    '?', '？', '좋아', '좋아요', '네', '아니요', '아니', '아니에요', '맞아', '알겠습니다', '수신',
    '음', '오', '알았어', '시작했어?', '돼', '안 돼', '되겠어', 'ok', 'yes', 'no',
    '네가 시작해', '테스트', '해봐', '봐봐',
}

STATE_ORG_MAP = {
    'SejaFinalReview': '세자', 'HongmungwanDraft': '홍문관', 'SaganwonFinalReview': '사간원', 'SeungjeongwonAssigned': '승정원',
    'InProgress': '진행중', 'FinalReview': '승정원', 'Completed': '완료', 'Blocked': '차단',
}

# State → Edict TaskState value 매핑
_STATE_TO_EDICT = {
    'SejaFinalReview': 'seja', 'HongmungwanDraft': 'hongmungwan', 'SaganwonFinalReview': 'saganwon',
    'SeungjeongwonAssigned': 'seungjeongwon', 'Ready': 'ready', 'InProgress': 'in_progress',
    'FinalReview': 'final_review', 'Completed': 'completed', 'Blocked': 'blocked',
    'Cancelled': 'cancelled', 'Pending': 'pending',
}


def _sanitize_text(raw, max_len=80):
    t = (raw or '').strip()
    t = re.split(r'\n*Conversation\b', t, maxsplit=1)[0].strip()
    t = re.split(r'\n*```', t, maxsplit=1)[0].strip()
    t = re.sub(r'[/\\.~][A-Za-z0-9_\-./]+(?:\.(?:py|js|ts|json|md|sh|yaml|yml|txt|csv|html|css|log))?', '', t)
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'^(전지|하교)([（(][^)）]*[)）])?[：:：]\s*', '', t)
    t = re.sub(r'(message_id|session_id|chat_id|open_id|user_id|tenant_key)\s*[:=]\s*\S+', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) > max_len:
        t = t[:max_len] + '…'
    return t


def _sanitize_title(raw):
    return _sanitize_text(raw, 80)


def _sanitize_remark(raw):
    return _sanitize_text(raw, 120)


def _is_valid_task_title(title):
    t = (title or '').strip()
    if len(t) < _MIN_TITLE_LEN:
        return False, f'제목이 너무 짧습니다 ({len(t)}<{_MIN_TITLE_LEN}자). 유효한 어명이 아닌 것 같습니다'
    if t.lower() in _JUNK_TITLES:
        return False, f'제목 "{t}"은(는) 유효한 어명이 아닙니다'
    if re.fullmatch(r'[\s?？!！.。,，…·\-—~]+', t):
        return False, '제목이 구두점만으로 이루어져 있습니다'
    if re.match(r'^[/\\~.]', t) or re.search(r'/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+', t):
        return False, f'제목이 파일 경로처럼 보입니다. 한국어로 업무를 요약해 주세요'
    if re.fullmatch(r'[\s\W]*', t):
        return False, '제목 정제 후 내용이 비어 있습니다'
    return True, ''


def _infer_agent_id():
    for k in ('OPENCLAW_AGENT_ID', 'OPENCLAW_AGENT', 'AGENT_ID'):
        v = (os.environ.get(k) or '').strip()
        if v:
            return v
    cwd = str(pathlib.Path.cwd())
    m = re.search(r'workspace-([a-zA-Z0-9_\-]+)', cwd)
    if m:
        return m.group(1)
    return 'system'


# ── API 클라이언트 ──

def _api_available() -> bool:
    """Edict API 사용 가능 여부 확인."""
    if EDICT_MODE == 'json':
        return False
    if EDICT_MODE == 'api':
        return True
    # auto 모드: 탐지
    try:
        import urllib.request
        req = urllib.request.Request(f"{EDICT_API_URL}/health", method='GET')
        req.add_header('Accept', 'application/json')
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _api_post(path: str, data: dict) -> dict | None:
    """Edict API에 POST 요청 전송."""
    try:
        import urllib.request
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            f"{EDICT_API_URL}{path}",
            data=body,
            method='POST',
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.warning(f'API 호출 실패 ({path}): {e}')
        return None


def _api_put(path: str, data: dict) -> dict | None:
    """Edict API에 PUT 요청 전송."""
    try:
        import urllib.request
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            f"{EDICT_API_URL}{path}",
            data=body,
            method='PUT',
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log.warning(f'API 호출 실패 ({path}): {e}')
        return None


# ── 명령어 → API 호출 ──

# API 사용 가능 여부 캐시
_api_ok = None


def _check_api():
    global _api_ok
    if _api_ok is None:
        _api_ok = _api_available()
        if _api_ok:
            log.debug('Edict API 사용 가능 — API 모드로 실행')
        else:
            log.debug('Edict API 사용 불가 — JSON 모드로 전환')
    return _api_ok


def _fallback_json():
    """폴백: 구버전 kanban_update 로직으로 전환."""
    # 같은 디렉토리의 구버전 구현으로 폴백
    old_path = pathlib.Path(__file__).parent / 'kanban_update_legacy.py'
    if old_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location('kanban_legacy', old_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return None


def cmd_create(task_id, title, state, org, official, remark=None):
    title = _sanitize_title(title)
    valid, reason = _is_valid_task_title(title)
    if not valid:
        log.warning(f'⚠️ {task_id} 생성 거부: {reason}')
        print(f'[칸반] 생성 거부: {reason}', flush=True)
        return

    if _check_api():
        edict_state = _STATE_TO_EDICT.get(state, state.lower())
        result = _api_post('/api/tasks', {
            'title': title,
            'description': remark or f'하교: {title}',
            'priority': '중',
            'assignee_org': org,
            'creator': official,
            'tags': [task_id],
            'meta': {'legacy_id': task_id, 'legacy_state': state},
        })
        if result:
            log.info(f'✅ {task_id} 생성 → Edict {result.get("task_id", "?")} | {title[:30]}')
            return

    # 폴백
    legacy = _fallback_json()
    if legacy:
        legacy.cmd_create(task_id, title, state, org, official, remark)
    else:
        log.error(f'업무 생성 실패: API 사용 불가 및 폴백 모듈 없음')


def cmd_state(task_id, new_state, now_text=None):
    if _check_api():
        edict_state = _STATE_TO_EDICT.get(new_state, new_state.lower())
        agent = _infer_agent_id()
        # legacy_id 태그로 edict task_id 조회 후 전이
        result = _api_post(f'/api/tasks/by-legacy/{task_id}/transition', {
            'new_state': edict_state,
            'agent': agent,
            'reason': now_text or f'상태 변경: {new_state}',
        })
        if result:
            log.info(f'✅ {task_id} 상태 변경 → {new_state}')
            return

    legacy = _fallback_json()
    if legacy:
        legacy.cmd_state(task_id, new_state, now_text)
    else:
        log.error(f'상태 변경 실패: API 사용 불가 및 폴백 모듈 없음')


def cmd_flow(task_id, from_dept, to_dept, remark):
    clean_remark = _sanitize_remark(remark)
    if _check_api():
        agent = _infer_agent_id()
        result = _api_post(f'/api/tasks/by-legacy/{task_id}/progress', {
            'agent': agent,
            'content': f'유관: {from_dept} → {to_dept} | {clean_remark}',
        })
        if result:
            log.info(f'✅ {task_id} 유관 기록: {from_dept} → {to_dept}')
            return

    legacy = _fallback_json()
    if legacy:
        legacy.cmd_flow(task_id, from_dept, to_dept, remark)


def cmd_done(task_id, output_path='', summary=''):
    if _check_api():
        agent = _infer_agent_id()
        result = _api_post(f'/api/tasks/by-legacy/{task_id}/transition', {
            'new_state': 'done',
            'agent': agent,
            'reason': summary or '업무가 완료되었습니다',
        })
        if result:
            log.info(f'✅ {task_id} 완료됨')
            return

    legacy = _fallback_json()
    if legacy:
        legacy.cmd_done(task_id, output_path, summary)


def cmd_block(task_id, reason):
    if _check_api():
        agent = _infer_agent_id()
        result = _api_post(f'/api/tasks/by-legacy/{task_id}/transition', {
            'new_state': 'blocked',
            'agent': agent,
            'reason': reason,
        })
        if result:
            log.warning(f'⚠️ {task_id} 차단됨: {reason}')
            return

    legacy = _fallback_json()
    if legacy:
        legacy.cmd_block(task_id, reason)


def cmd_progress(task_id, now_text, todos_pipe='', tokens=0, cost=0.0, elapsed=0):
    clean = _sanitize_remark(now_text)

    # todos 파싱
    parsed_todos = None
    if todos_pipe:
        new_todos = []
        for i, item in enumerate(todos_pipe.split('|'), 1):
            item = item.strip()
            if not item:
                continue
            if item.endswith('✅'):
                status = 'completed'
                title = item[:-1].strip()
            elif item.endswith('🔄'):
                status = 'in-progress'
                title = item[:-1].strip()
            else:
                status = 'not-started'
                title = item
            new_todos.append({'id': str(i), 'title': title, 'status': status})
        if new_todos:
            parsed_todos = new_todos

    if _check_api():
        agent = _infer_agent_id()
        # 진행 상황 업데이트
        _api_post(f'/api/tasks/by-legacy/{task_id}/progress', {
            'agent': agent,
            'content': clean,
        })
        # todos 업데이트
        if parsed_todos:
            _api_put(f'/api/tasks/by-legacy/{task_id}/todos', {
                'todos': parsed_todos,
            })
        log.info(f'📡 {task_id} 진행: {clean[:40]}...')
        return

    legacy = _fallback_json()
    if legacy:
        legacy.cmd_progress(task_id, now_text, todos_pipe, tokens, cost, elapsed)


def cmd_todo(task_id, todo_id, title, status='not-started', detail=''):
    if status not in ('not-started', 'in-progress', 'completed'):
        status = 'not-started'

    if _check_api():
        # 기존 todos 조회 후 업데이트 (여기서는 간략히 진행 업데이트로 처리)
        agent = _infer_agent_id()
        _api_post(f'/api/tasks/by-legacy/{task_id}/progress', {
            'agent': agent,
            'content': f'Todo #{todo_id}: {title} → {status}',
        })
        log.info(f'✅ {task_id} todo: {todo_id} → {status}')
        return

    legacy = _fallback_json()
    if legacy:
        legacy.cmd_todo(task_id, todo_id, title, status, detail)


# ── CLI 분기 ──

_CMD_MIN_ARGS = {
    'create': 6, 'state': 3, 'flow': 5, 'done': 2, 'block': 3, 'todo': 4, 'progress': 3,
}

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    if cmd in _CMD_MIN_ARGS and len(args) < _CMD_MIN_ARGS[cmd]:
        print(f'오류: "{cmd}" 명령은 최소 {_CMD_MIN_ARGS[cmd]}개의 인수가 필요합니다. 실제 {len(args)}개')
        print(__doc__)
        sys.exit(1)

    if cmd == 'create':
        cmd_create(args[1], args[2], args[3], args[4], args[5], args[6] if len(args) > 6 else None)
    elif cmd == 'state':
        cmd_state(args[1], args[2], args[3] if len(args) > 3 else None)
    elif cmd == 'flow':
        cmd_flow(args[1], args[2], args[3], args[4])
    elif cmd == 'done':
        cmd_done(args[1], args[2] if len(args) > 2 else '', args[3] if len(args) > 3 else '')
    elif cmd == 'block':
        cmd_block(args[1], args[2])
    elif cmd == 'todo':
        todo_pos = []
        todo_detail = ''
        ti = 1
        while ti < len(args):
            if args[ti] == '--detail' and ti + 1 < len(args):
                todo_detail = args[ti + 1]; ti += 2
            else:
                todo_pos.append(args[ti]); ti += 1
        cmd_todo(
            todo_pos[0] if len(todo_pos) > 0 else '',
            todo_pos[1] if len(todo_pos) > 1 else '',
            todo_pos[2] if len(todo_pos) > 2 else '',
            todo_pos[3] if len(todo_pos) > 3 else 'not-started',
            detail=todo_detail,
        )
    elif cmd == 'progress':
        pos_args = []
        kw = {}
        i = 1
        while i < len(args):
            if args[i] == '--tokens' and i + 1 < len(args):
                kw['tokens'] = args[i + 1]; i += 2
            elif args[i] == '--cost' and i + 1 < len(args):
                kw['cost'] = args[i + 1]; i += 2
            elif args[i] == '--elapsed' and i + 1 < len(args):
                kw['elapsed'] = args[i + 1]; i += 2
            else:
                pos_args.append(args[i]); i += 1
        cmd_progress(
            pos_args[0] if len(pos_args) > 0 else '',
            pos_args[1] if len(pos_args) > 1 else '',
            pos_args[2] if len(pos_args) > 2 else '',
            tokens=kw.get('tokens', 0),
            cost=kw.get('cost', 0.0),
            elapsed=kw.get('elapsed', 0),
        )
    else:
        print(__doc__)
        sys.exit(1)
