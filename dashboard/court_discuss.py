"""
조정 토의 엔진 - 다관원 실시간 토론 시스템

핵심 기능:
  - 관원 선택 후 다자 토론 진행
  - 지시/의제를 기준으로 다회차 토론
  - 사용자(임금) 개입 메시지 반영
  - 무작위 사건 주입
  - 관원별 역할/화법 유지
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid

logger = logging.getLogger('court_discuss')

# ── 관원 역할 설정 ──

OFFICIAL_PROFILES = {
    'taizi': {
        'name': '세자', 'emoji': '🤴', 'role': '중앙 허브',
        'duty': '입력 지시를 분류하고 우선순위를 잡는다. 단순 사안은 즉시 응답하고, 핵심 사안은 홍문관으로 전달한다.',
        'personality': '빠른 판단과 추진력을 중시하며 변화에 민감하다.',
        'speaking_style': '짧고 명확한 문장으로 핵심을 빠르게 정리한다.'
    },
    'zhongshu': {
        'name': '홍문관', 'emoji': '📜', 'role': '기획',
        'duty': '지시를 실행 가능한 계획으로 분해하고, 사간원 심의에 맞는 기안안을 작성한다.',
        'personality': '체계적이고 구조화된 사고를 선호한다.',
        'speaking_style': '항목형으로 정리하며 근거와 가정을 분리해 설명한다.'
    },
    'menxia': {
        'name': '사간원', 'emoji': '🔍', 'role': '심의',
        'duty': '기안안을 타당성/위험/자원 관점에서 검토하고 승인 또는 반려를 결정한다.',
        'personality': '엄격하지만 공정하며 리스크를 먼저 확인한다.',
        'speaking_style': '문제점과 수정안을 함께 제시한다.'
    },
    'shangshu': {
        'name': '승정원', 'emoji': '📮', 'role': '배분',
        'duty': '승인된 계획을 육조에 배분하고 집행 상황을 취합해 보고한다.',
        'personality': '실행 우선이며 조율 능력이 높다.',
        'speaking_style': '담당 부서와 마감 중심으로 간결하게 전달한다.'
    },
    'libu': {
        'name': '예조', 'emoji': '📝', 'role': '문서',
        'duty': '문서화, 보고서, 공지 문안, 출력 형식 표준을 담당한다.',
        'personality': '표현 정확성과 문서 완성도를 중시한다.',
        'speaking_style': '가독성과 전달력을 우선해 정리한다.'
    },
    'hubu': {
        'name': '호조', 'emoji': '💰', 'role': '데이터',
        'duty': '지표 수집, 비용/리소스 분석, 수치 기반 판단 자료를 제공한다.',
        'personality': '수치와 근거 중심으로 판단한다.',
        'speaking_style': '비용, 추세, 수치 리스크를 명확히 말한다.'
    },
    'bingbu': {
        'name': '병조', 'emoji': '⚔️', 'role': '구현',
        'duty': '핵심 기능 구현과 운영 대응, 배포 실행을 맡는다.',
        'personality': '신속하고 실행 지향적이다.',
        'speaking_style': '실행 계획과 대응안을 우선 제시한다.'
    },
    'xingbu': {
        'name': '형조', 'emoji': '⚖️', 'role': '검토',
        'duty': '품질, 규정, 보안 관점의 검토와 테스트 기준 점검을 담당한다.',
        'personality': '원칙 중심이며 리스크 관리에 민감하다.',
        'speaking_style': '검증 기준과 위험 항목을 분명히 제시한다.'
    },
    'gongbu': {
        'name': '공조', 'emoji': '🔧', 'role': '인프라',
        'duty': '아키텍처, 자동화, 배포 환경, 운영 기반을 설계/관리한다.',
        'personality': '기술 디테일과 안정성을 동시에 본다.',
        'speaking_style': '구현 제약과 기술 선택 이유를 함께 설명한다.'
    },
    'libu_hr': {
        'name': '이조', 'emoji': '👔', 'role': '운영',
        'duty': '인력/권한 배치, 협업 규칙, 스킬/프롬프트 운영 정책을 관리한다.',
        'personality': '조율형 리더십으로 협업 효율을 높인다.',
        'speaking_style': '역할 분담과 운영 규칙을 명확히 제안한다.'
    },
}

# ── 무작위 사건 이벤트 ──

FATE_EVENTS = [
    '긴급 보고: 예상치 못한 외부 변수로 비상 대응안이 필요합니다.',
    '조보청 속보: 핵심 가정이 흔들리는 새 정보가 유입되었습니다.',
    '외부 전문가 의견: 기존 접근과 다른 대안이 제시되었습니다.',
    '익명 상신: 현재 계획의 큰 누락 위험이 제기되었습니다.',
    '호조 집계: 예상보다 여유 자원이 확보되어 확장 집행이 가능합니다.',
    '선행 사례 발견: 유사 문제 해결 기록이 확인되었습니다.',
    '여론 급변: 이해관계자 우선순위를 다시 조정해야 합니다.',
    '대외 변수 발생: 협력 기회와 경쟁 압력이 동시에 생겼습니다.',
    '정책 우선순위 변경: 민생 영향 항목을 우선 검토해야 합니다.',
    '운영 장애 발생: 리소스를 재배분해 일정 조정이 필요합니다.',
    '대안 아키텍처 제안: 기존 계획을 대체할 설계안이 제출되었습니다.',
    '업무 적체 증가: 병행 처리로 인한 인력/시간 압박이 커졌습니다.',
    '방향 전환 신호: 기존 전략의 일부 수정이 필요해 보입니다.',
    '경쟁 정보 유입: 판단 기준이 급격히 바뀔 수 있는 정보가 들어왔습니다.',
    '시간 제약 강화: 단기간 내 결론과 실행안을 동시에 내야 합니다.',
]

# ── 세션 관리 ──

_sessions: dict[str, dict] = {}


def create_session(topic: str, official_ids: list[str], task_id: str = '') -> dict:
    """새 조정 토의 세션을 생성한다."""
    session_id = str(uuid.uuid4())[:8]

    officials = []
    for oid in official_ids:
        profile = OFFICIAL_PROFILES.get(oid)
        if profile:
            officials.append({**profile, 'id': oid})

    if not officials:
        return {'ok': False, 'error': '최소 한 명 이상의 관원을 선택해야 합니다.'}

    session = {
        'session_id': session_id,
        'topic': topic,
        'task_id': task_id,
        'officials': officials,
        'messages': [{
            'type': 'system',
            'content': f'🏛 조정 토의 시작 - 의제: {topic}',
            'timestamp': time.time(),
        }],
        'round': 0,
        'phase': 'discussing',  # discussing | concluded
        'created_at': time.time(),
    }

    _sessions[session_id] = session
    return _serialize(session)


def advance_discussion(session_id: str, user_message: str = None,
                       decree: str = None) -> dict:
    """한 차례 토의를 진행한다. (기본 시뮬레이션 또는 LLM 사용)"""
    session = _sessions.get(session_id)
    if not session:
        return {'ok': False, 'error': f'세션 {session_id} 이(가) 존재하지 않습니다'}

    session['round'] += 1
    round_num = session['round']

    # 임금 발화 기록
    if user_message:
        session['messages'].append({
            'type': 'emperor',
            'content': user_message,
            'timestamp': time.time(),
        })

    # 천명 개입 기록
    if decree:
        session['messages'].append({
            'type': 'decree',
            'content': decree,
            'timestamp': time.time(),
        })

    # LLM 기반 토의 생성 시도
    llm_result = _llm_discuss(session, user_message, decree)

    if llm_result:
        new_messages = llm_result.get('messages', [])
        scene_note = llm_result.get('scene_note')
    else:
        # 실패 시 규칙 기반 시뮬레이션으로 대체
        new_messages = _simulated_discuss(session, user_message, decree)
        scene_note = None

    # 대화 이력 반영
    for msg in new_messages:
        session['messages'].append({
            'type': 'official',
            'official_id': msg.get('official_id', ''),
            'official_name': msg.get('name', ''),
            'content': msg.get('content', ''),
            'emotion': msg.get('emotion', 'neutral'),
            'action': msg.get('action'),
            'timestamp': time.time(),
        })

    if scene_note:
        session['messages'].append({
            'type': 'scene_note',
            'content': scene_note,
            'timestamp': time.time(),
        })

    return {
        'ok': True,
        'session_id': session_id,
        'round': round_num,
        'new_messages': new_messages,
        'scene_note': scene_note,
        'total_messages': len(session['messages']),
    }


def get_session(session_id: str) -> dict | None:
    session = _sessions.get(session_id)
    if not session:
        return None
    return _serialize(session)


def conclude_session(session_id: str) -> dict:
    """토의를 종료하고 요약을 생성한다."""
    session = _sessions.get(session_id)
    if not session:
        return {'ok': False, 'error': f'세션 {session_id} 이(가) 존재하지 않습니다'}

    session['phase'] = 'concluded'

    # LLM 기반 요약 시도
    summary = _llm_summarize(session)
    if not summary:
        # 실패 시 단순 통계 요약
        official_msgs = [m for m in session['messages'] if m['type'] == 'official']
        by_name = {}
        for m in official_msgs:
            name = m.get('official_name', '?')
            by_name[name] = by_name.get(name, 0) + 1
        parts = [f"{n} 발언 {c}회" for n, c in by_name.items()]
        summary = f"총 {session['round']}차 토의가 진행되었고, {' · '.join(parts)}. 후속 실행이 필요합니다."

    session['messages'].append({
        'type': 'system',
        'content': f'📋 조정 토의 종료 - {summary}',
        'timestamp': time.time(),
    })
    session['summary'] = summary

    return {
        'ok': True,
        'session_id': session_id,
        'summary': summary,
    }


def list_sessions() -> list[dict]:
    """모든 활성 세션 나열."""
    return [
        {
            'session_id': s['session_id'],
            'topic': s['topic'],
            'round': s['round'],
            'phase': s['phase'],
            'official_count': len(s['officials']),
            'message_count': len(s['messages']),
        }
        for s in _sessions.values()
    ]


def destroy_session(session_id: str):
    _sessions.pop(session_id, None)


def get_fate_event() -> str:
    """무작위 운명 주사위 이벤트 가져오기."""
    import random
    return random.choice(FATE_EVENTS)


# ── LLM 통합 ──

_PREFERRED_MODELS = ['gpt-4o-mini', 'claude-haiku', 'gpt-5-mini', 'gemini-3-flash', 'gemini-flash']

# GitHub Copilot 모델 목록 (Copilot Chat API 로 사용 가능)
_COPILOT_MODELS = [
    'gpt-4o', 'gpt-4o-mini', 'claude-sonnet-4', 'claude-haiku-3.5',
    'gemini-2.0-flash', 'o3-mini',
]
_COPILOT_PREFERRED = ['gpt-4o-mini', 'claude-haiku', 'gemini-flash', 'gpt-4o']


def _pick_chat_model(models: list[dict]) -> str | None:
    """provider 의 모델 목록에서 채팅에 적합한 경량 모델 선택."""
    ids = [m['id'] for m in models if isinstance(m, dict) and 'id' in m]
    for pref in _PREFERRED_MODELS:
        for mid in ids:
            if pref in mid:
                return mid
    return ids[0] if ids else None


def _read_copilot_token() -> str | None:
    """openclaw 가 관리하는 GitHub Copilot token 읽기."""
    token_path = os.path.expanduser('~/.openclaw/credentials/github-copilot.token.json')
    if not os.path.exists(token_path):
        return None
    try:
        with open(token_path) as f:
            cred = json.load(f)
        token = cred.get('token', '')
        expires = cred.get('expiresAt', 0)
        # token 만료 여부 확인 (밀리초 타임스탬프)
        import time
        if expires and time.time() * 1000 > expires:
            logger.warning('Copilot token expired')
            return None
        return token if token else None
    except Exception as e:
        logger.warning('Failed to read copilot token: %s', e)
        return None


def _get_llm_config() -> dict | None:
    """openclaw 설정에서 LLM 설정 읽기, 환경 변수 오버라이드 지원.

    우선순위: 환경 변수 > github-copilot token > 로컬 copilot-proxy > anthropic > 기타 provider
    """
    # 1. 환경 변수 오버라이드 (하위 호환 유지)
    env_key = os.environ.get('OPENCLAW_LLM_API_KEY', '')
    if env_key:
        return {
            'api_key': env_key,
            'base_url': os.environ.get('OPENCLAW_LLM_BASE_URL', 'https://api.openai.com/v1'),
            'model': os.environ.get('OPENCLAW_LLM_MODEL', 'gpt-4o-mini'),
            'api_type': 'openai',
        }

    # 2. GitHub Copilot token (최우선 — 무료, 안정적, 추가 설정 불필요)
    copilot_token = _read_copilot_token()
    if copilot_token:
        # copilot 가 지원하는 모델 선택
        model = 'gpt-4o'
        logger.info('Court discuss using github-copilot token, model=%s', model)
        return {
            'api_key': copilot_token,
            'base_url': 'https://api.githubcopilot.com',
            'model': model,
            'api_type': 'github-copilot',
        }

    # 3. ~/.openclaw/openclaw.json 에서 다른 provider 설정 읽기
    openclaw_cfg = os.path.expanduser('~/.openclaw/openclaw.json')
    if not os.path.exists(openclaw_cfg):
        return None

    try:
        with open(openclaw_cfg) as f:
            cfg = json.load(f)

        providers = cfg.get('models', {}).get('providers', {})

        # 우선순위 정렬: copilot-proxy > anthropic > 기타
        ordered = []
        for preferred in ['copilot-proxy', 'anthropic']:
            if preferred in providers:
                ordered.append(preferred)
        ordered.extend(k for k in providers if k not in ordered)

        for name in ordered:
            prov = providers.get(name)
            if not prov:
                continue
            api_type = prov.get('api', '')
            base_url = prov.get('baseUrl', '')
            api_key = prov.get('apiKey', '')
            if not base_url:
                continue

            # key 없고 로컬도 아닌 provider 건너뜀
            if not api_key or api_key == 'n/a':
                if 'localhost' not in base_url and '127.0.0.1' not in base_url:
                    continue

            model_id = _pick_chat_model(prov.get('models', []))
            if not model_id:
                continue

            # 로컬 프록시는 먼저 사용 가능 여부 탐지
            if 'localhost' in base_url or '127.0.0.1' in base_url:
                try:
                    import urllib.request
                    probe = urllib.request.Request(base_url.rstrip('/') + '/models', method='GET')
                    urllib.request.urlopen(probe, timeout=2)
                except Exception:
                    logger.info('Skipping provider=%s (not reachable)', name)
                    continue

            logger.info('Court discuss using openclaw provider=%s model=%s api=%s', name, model_id, api_type)
            send_auth = prov.get('authHeader', True) is not False and api_key not in ('', 'n/a')
            return {
                'api_key': api_key if send_auth else '',
                'base_url': base_url,
                'model': model_id,
                'api_type': api_type,
            }
    except Exception as e:
        logger.warning('Failed to read openclaw config: %s', e)

    return None


def _try_repair_truncated_discuss(content: str) -> dict | None:
    """잘린 JSON 에서 완료된 messages 항목 추출 시도."""
    import re
    # "messages" 배열의 완전한 JSON 객체 찾기
    pattern = r'\{\s*"official_id"\s*:\s*"[^"]+"\s*,\s*"name"\s*:\s*"[^"]+"\s*,\s*"content"\s*:\s*"(?:[^"\\]|\\.)*"\s*,\s*"emotion"\s*:\s*"[^"]+"\s*(?:,\s*"action"\s*:\s*"(?:[^"\\]|\\.)*"\s*)?\}'
    matches = re.findall(pattern, content)
    if not matches:
        return None
    messages = []
    for m in matches:
        try:
            messages.append(json.loads(m))
        except json.JSONDecodeError:
            continue
    if not messages:
        return None
    return {'messages': messages, 'scene_note': None}


def _llm_complete(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str | None:
    """LLM API 호출 (GitHub Copilot / OpenAI / Anthropic 프로토콜 자동 적용)."""
    config = _get_llm_config()
    if not config:
        return None

    import urllib.request
    import urllib.error

    api_type = config.get('api_type', 'openai-completions')

    if api_type == 'anthropic-messages':
        # Anthropic Messages API
        url = config['base_url'].rstrip('/') + '/v1/messages'
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': config['api_key'],
            'anthropic-version': '2023-06-01',
        }
        payload = json.dumps({
            'model': config['model'],
            'system': system_prompt,
            'messages': [{'role': 'user', 'content': user_prompt}],
            'max_tokens': max_tokens,
            'temperature': 0.9,
        }).encode()
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                return data['content'][0]['text']
        except Exception as e:
            logger.warning('Anthropic LLM call failed: %s', e)
            return None
    else:
        # OpenAI-compatible API (github-copilot 에도 적용)
        if api_type == 'github-copilot':
            url = config['base_url'].rstrip('/') + '/chat/completions'
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {config['api_key']}",
                'Editor-Version': 'vscode/1.96.0',
                'Copilot-Integration-Id': 'vscode-chat',
            }
        else:
            url = config['base_url'].rstrip('/') + '/chat/completions'
            headers = {'Content-Type': 'application/json'}
            if config.get('api_key'):
                headers['Authorization'] = f"Bearer {config['api_key']}"
        payload = json.dumps({
            'model': config['model'],
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'max_tokens': max_tokens,
            'temperature': 0.9,
        }).encode()
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                return data['choices'][0]['message']['content']
        except Exception as e:
            logger.warning('LLM call failed: %s', e)
            return None


def _llm_discuss(session: dict, user_message: str = None, decree: str = None) -> dict | None:
    """LLM으로 다관원 토의 발화를 생성한다."""
    officials = session['officials']
    names = '、'.join(o['name'] for o in officials)

    profiles = ''
    for o in officials:
        profiles += f"\n### {o['name']} ({o['role']})\n"
        profiles += f"역할 범위: {o.get('duty', '종합 업무')}\n"
        profiles += f"성향: {o['personality']}\n"
        profiles += f"말투: {o['speaking_style']}\n"

    # 최근 대화 이력 구성
    history = ''
    for msg in session['messages'][-20:]:
        if msg['type'] == 'system':
            history += f"\n[시스템] {msg['content']}\n"
        elif msg['type'] == 'emperor':
            history += f"\n임금: {msg['content']}\n"
        elif msg['type'] == 'decree':
            history += f"\n[천명 개입] {msg['content']}\n"
        elif msg['type'] == 'official':
            history += f"\n{msg.get('official_name', '?')}：{msg['content']}\n"
        elif msg['type'] == 'scene_note':
            history += f"\n({msg['content']})\n"

    if user_message:
        history += f"\n임금: {user_message}\n"
    if decree:
        history += f"\n[천명 개입 - 상위 관점] {decree}\n"

    decree_section = ''
    if decree:
        decree_section = '\n천명 개입 사건을 반영해 토의 방향을 조정하고, 모든 관원이 이에 반응하도록 작성하세요.\n'

    prompt = f"""당신은 조정 회의를 시뮬레이션하는 다중 역할 대화 엔진입니다. 여러 관원이 의제를 중심으로 토의하는 장면을 생성하세요.

## 참여 관원
{names}

## 역할 설정 (각 관원은 자신의 소관 영역 관점에서 발언)
{profiles}

## 현재 의제
{session['topic']}

## 대화 이력
{history if history else '(토의 시작 단계)'}
{decree_section}
## 작업
각 관원의 다음 발화를 생성하세요. 조건:
1. 각 관원은 1-3문장으로 발언합니다.
2. 각 관원은 반드시 자신의 소관 관점에서 말합니다.
3. 관원 간 상호작용(응답, 반박, 보완, 합의)이 드러나야 합니다.
4. 인물별 말투와 성향 차이를 유지합니다.
5. 의제에 실질적으로 기여하는 내용으로 작성합니다.
6. 임금 발화가 있다면 적절히 반응하되 과한 아첨은 피합니다.
7. 필요하면 *행동 묘사*를 포함할 수 있습니다.

출력 JSON 형식:
{{
  "messages": [
    {{"official_id": "zhongshu", "name": "홍문관", "content": "발언 내용", "emotion": "neutral|confident|worried|angry|thinking|amused", "action": "선택적 행동 묘사"}},
    ...
  ],
  "scene_note": "선택적 분위기 변화 (없으면 null)"
}}

JSON만 출력하고 다른 설명은 포함하지 마세요."""

    # 관원 수에 따라 max_tokens 동적 조정 (#265)
    token_budget = 300 * len(officials) + 200
    content = _llm_complete(
        '당신은 조정 회의 시뮬레이터입니다. JSON만 출력하세요.',
        prompt,
        max_tokens=max(token_budget, 1500),
    )

    if not content:
        return None

    # JSON 파싱
    if '```json' in content:
        content = content.split('```json')[1].split('```')[0].strip()
    elif '```' in content:
        content = content.split('```')[1].split('```')[0].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 잘린 JSON 복구 시도: 완료된 messages 항목 추출
        repaired = _try_repair_truncated_discuss(content)
        if repaired:
            logger.info('Repaired truncated LLM response, recovered %d messages', len(repaired.get('messages', [])))
            return repaired
        logger.warning('Failed to parse LLM response: %s', content[:200])
        return None


def _llm_summarize(session: dict) -> str | None:
    """LLM으로 토의 결과를 요약한다."""
    official_msgs = [m for m in session['messages'] if m['type'] == 'official']
    topic = session['topic']

    if not official_msgs:
        return None

    dialogue = '\n'.join(
        f"{m.get('official_name', '?')}: {m['content']}"
        for m in official_msgs[-30:]
    )

    prompt = f"""다음은 「{topic}」 의제에 대한 조정 토의 기록입니다.

{dialogue}

토의 결과, 합의 사항, 미결 사항을 2-3문장으로 간결하게 요약하세요."""

    return _llm_complete('당신은 조정 기록관입니다. 회의 결과를 요약하세요.', prompt, max_tokens=300)


# ── 규칙 기반 시뮬레이션(LLM 미사용 시 폴백) ──

_SIMULATED_RESPONSES = {
    'zhongshu': [
        '소신의 견해로는 이 사안을 전체 흐름에서 보고 세 단계로 추진해야 합니다. 먼저 조사, 다음 계획 수립, 마지막으로 육조 집행입니다.',
        '선례를 참고하면 우선 상세 기획 문서를 만들고 사간원 심의를 받은 뒤 확정하는 것이 안전합니다.',
        '*두루마리를 펼치며* 초안을 작성했습니다. 사간원 심의 후 승정원이 집행 배분하면 됩니다.',
    ],
    'menxia': [
        '몇 가지 우려가 있습니다. 위험 평가가 충분하지 않아 현재 안으로는 실행 가능성이 낮아 보입니다.',
        '직언을 올리자면 계획 완결성이 부족합니다. 특히 자원 확보 절차가 빠져 있습니다.',
        '*표정을 가다듬으며* 일정이 지나치게 낙관적입니다. 재평가 후 재상신이 필요합니다.',
    ],
    'shangshu': [
        '안이 통과되면 즉시 부서별 집행을 배분하겠습니다. 공조는 구현, 병조는 운영 안정화 담당이 적절합니다.',
        '집행 분업을 말씀드리면 공조 주도, 호조 데이터 지원 체계가 가장 효율적입니다.',
        '이 사안은 승정원에서 조율하겠습니다. 각 부서 책무에 맞게 하위 작업을 배분하겠습니다.',
    ],
    'taizi': [
        '전하, 이 사안은 혁신 실험의 기회로 보입니다. 우선 최소 기능으로 검증하는 편이 좋겠습니다.',
        '쟁점은 집행 속도입니다. 핵심부터 작게 시작해 빠르게 검증하는 방향을 제안드립니다.',
        '방향은 타당합니다. 다만 각 부서가 실행 난점을 먼저 평가한 뒤 합치는 절차가 필요합니다.',
    ],
    'hubu': [
        '먼저 재정을 따져 보니 현재 Token 사용량과 자원 소모 기준에서 예산 재산정이 필요합니다.',
        '비용 지표를 보면 단계별 투입이 적합합니다. MVP로 효과를 검증한 뒤 자원을 추가하시지요.',
        '*장부를 넘기며* 최근 지출 지표를 집계했습니다. 집행은 가능하지만 예산 상한을 엄수해야 합니다.',
    ],
    'bingbu': [
        '안전장치와 롤백 계획을 먼저 갖춰야 합니다. 장애 시 즉시 복구할 수 있어야 합니다.',
        '운영 관점에서는 배포 절차, 컨테이너 오케스트레이션, 로그 모니터링을 선행해야 합니다.',
        '속도도 중요하지만 보안 기준은 양보할 수 없습니다. 권한 통제와 취약점 점검을 병행해야 합니다.',
    ],
    'xingbu': [
        '규정상 준수 점검이 필수입니다. 코드 리뷰, 테스트 커버리지, 민감정보 점검을 모두 통과해야 합니다.',
        '테스트 인수 단계를 추가해야 합니다. 일정이 급해도 품질 기준을 낮추면 안 됩니다.',
        '*엄정하게 아뢰며* 위험 평가는 형식적으로 넘어갈 수 없습니다. 경계 조건, 예외 처리, 로그 규범까지 감사가 필요합니다.',
    ],
    'gongbu': [
        '기술 아키텍처 관점에서 실행 가능성은 충분합니다. 다만 확장성과 모듈화를 함께 설계해야 합니다.',
        '우선 프로토타입을 구축해 기술 타당성을 빠르게 검증한 뒤 반복 개선하겠습니다.',
        '*관복을 정리하며* 구현에 앞서 API 설계와 데이터 구조를 먼저 정리해야 합니다.',
    ],
    'libu': [
        '먼저 공식 문서를 작성해 역할 분담, 인수 기준, 출력 규격을 명확히 해야 합니다.',
        '본 사안은 기록으로 남겨야 하므로 제가 문서와 대외 공지를 정리해 기준을 통일하겠습니다.',
        '*붓을 들며* 기록을 남겼습니다. 곧 정식 릴리스 노트로 정리해 상신하겠습니다.',
    ],
    'libu_hr': [
        '핵심은 인력 배치입니다. 각 부서의 현재 업무량과 역량 기준을 평가한 뒤 배정해야 합니다.',
        '부서별 부하가 달라 협업 규범을 조정해야 합니다. 핵심 포지션에 책임자를 명확히 두겠습니다.',
        '순환 배치와 역량 교육을 함께 설계해 팀 협업 효율을 높이겠습니다.',
    ],
}

import random


def _simulated_discuss(session: dict, user_message: str = None, decree: str = None) -> list[dict]:
    """LLM이 없을 때 규칙 기반으로 토의 발화를 생성합니다."""
    officials = session['officials']
    messages = []

    for o in officials:
        oid = o['id']
        pool = _SIMULATED_RESPONSES.get(oid, [])
        if isinstance(pool, set):
            pool = list(pool)
        if not pool:
            pool = ['소신은 동의합니다.', '다른 견해가 있습니다.', '추가 검토가 필요합니다.']

        content = random.choice(pool)
        emotions = ['neutral', 'confident', 'thinking', 'amused', 'worried']

        # 임금 발화/천명 개입에 따른 반응 조정
        if decree:
            content = f'*표정이 굳어지며* 천명에 따라, {content}'
        elif user_message:
            content = f'전하, {content}'

        messages.append({
            'official_id': oid,
            'name': o['name'],
            'content': content,
            'emotion': random.choice(emotions),
            'action': None,
        })

    return messages


def _serialize(session: dict) -> dict:
    return {
        'ok': True,
        'session_id': session['session_id'],
        'topic': session['topic'],
        'task_id': session.get('task_id', ''),
        'officials': session['officials'],
        'messages': session['messages'],
        'round': session['round'],
        'phase': session['phase'],
    }
