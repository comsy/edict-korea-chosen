# 🚨 OpenClaw Harness Orchestrator — 즉시 수정 항목

> **작성일**: 2026-04-29
> **분류**: Critical / 운영 차단
> **대상**: `edict-korea-chosen`을 OpenClaw 멀티 에이전트 Harness Orchestrator로 사용할 때 즉시 깨지는 결함

---

## 개요

이 문서는 **운영 환경에서 즉시 깨지거나, 사용자가 처음 실행할 때 차단되는 결함**만 모았습니다. 지금 당장 수정하지 않으면 `kanban_update_edict.py state ...` 같은 명령이 호출 즉시 HTTP 400을 반환합니다.

---

## 1. 🔴 `kanban_update_edict.py` ↔ Backend 상태값 매핑 미스매치

### 현황

[`edict/scripts/kanban_update_edict.py:48-53`](../edict/scripts/kanban_update_edict.py)는 상태를 **소문자**로 변환합니다:

```python
_STATE_TO_EDICT = {
    'SejaFinalReview': 'seja',
    'HongmungwanDraft': 'hongmungwan',
    'SaganwonFinalReview': 'saganwon',
    'SeungjeongwonAssigned': 'seungjeongwon',
    'Ready': 'ready',
    'InProgress': 'in_progress',
    'FinalReview': 'final_review',
    'Completed': 'completed',
    'Blocked': 'blocked',
    'Cancelled': 'cancelled',
    'Pending': 'pending',
}
```

### 백엔드 측 검증 로직

[`edict/backend/app/api/legacy.py:64`](../edict/backend/app/api/legacy.py)는 `TaskState` enum으로 검증합니다:

```python
try:
    new_state = TaskState(body.new_state)
except ValueError:
    raise HTTPException(status_code=400, detail=f"Invalid state: {body.new_state}")
```

[`edict/backend/app/models/task.py`](../edict/backend/app/models/task.py)의 `TaskState` enum 값은 **PascalCase**입니다:

```python
class TaskState(str, enum.Enum):
    SejaFinalReview = "SejaFinalReview"
    HongmungwanDraft = "HongmungwanDraft"
    SaganwonFinalReview = "SaganwonFinalReview"
    SeungjeongwonAssigned = "SeungjeongwonAssigned"
    Ready = "Ready"
    InProgress = "InProgress"
    FinalReview = "FinalReview"
    Completed = "Completed"
    Blocked = "Blocked"
    Cancelled = "Cancelled"
    Pending = "Pending"
    PendingConfirm = "PendingConfirm"
```

### 결과

```bash
$ python3 kanban_update_edict.py state JJC-20260429-001 SejaFinalReview "분류 완료"
# → POST /api/tasks/by-legacy/JJC-20260429-001/transition
#    {"new_state": "seja", ...}
# → 400 Bad Request: Invalid state: seja
```

### 수정 방안

**옵션 A (권장)**: `_STATE_TO_EDICT`를 **identity 매핑**으로 변경하여 PascalCase 그대로 전달.

```python
# edict/scripts/kanban_update_edict.py
_STATE_TO_EDICT = {
    'SejaFinalReview': 'SejaFinalReview',
    'HongmungwanDraft': 'HongmungwanDraft',
    'SaganwonFinalReview': 'SaganwonFinalReview',
    'SeungjeongwonAssigned': 'SeungjeongwonAssigned',
    'Ready': 'Ready',
    'InProgress': 'InProgress',
    'FinalReview': 'FinalReview',
    'Completed': 'Completed',
    'Blocked': 'Blocked',
    'Cancelled': 'Cancelled',
    'Pending': 'Pending',
    'PendingConfirm': 'PendingConfirm',
}
```

또는 `_STATE_TO_EDICT` 딕셔너리를 제거하고 `state`를 그대로 전달.

**옵션 B**: 백엔드 `legacy.py`에서 소문자 입력도 받아 PascalCase로 정규화.

```python
# edict/backend/app/api/legacy.py
_LEGACY_STATE_ALIAS = {
    'seja': 'SejaFinalReview',
    'hongmungwan': 'HongmungwanDraft',
    'saganwon': 'SaganwonFinalReview',
    'seungjeongwon': 'SeungjeongwonAssigned',
    'ready': 'Ready',
    'in_progress': 'InProgress',
    'final_review': 'FinalReview',
    'completed': 'Completed',
    'done': 'Completed',  # 항목 #2 동시 해결
    'blocked': 'Blocked',
    'cancelled': 'Cancelled',
    'pending': 'Pending',
}

# legacy_transition() 안에서
canonical = _LEGACY_STATE_ALIAS.get(body.new_state, body.new_state)
new_state = TaskState(canonical)
```

> **권장**: 옵션 A + 옵션 B 동시 적용. 클라이언트는 정확한 enum 값을 보내고, 백엔드는 방어적 정규화로 호환성 보장.

### 검증 절차

```bash
# 1) 작업 생성
python3 edict/scripts/kanban_update_edict.py create JJC-TEST-001 "테스트 어명 (8자 이상 필요)" hongmungwan 홍문관 홍문학사

# 2) 상태 변경 — 수정 전: HTTP 400, 수정 후: HTTP 200
python3 edict/scripts/kanban_update_edict.py state JJC-TEST-001 HongmungwanDraft "초안 작성 시작"

# 3) 백엔드 로그에서 transition 성공 메시지 확인
tail -f logs/server.log | grep "state:"
```

---

## 2. 🔴 `cmd_done`이 존재하지 않는 상태값 'done' 전송

### 현황

[`edict/scripts/kanban_update_edict.py:264`](../edict/scripts/kanban_update_edict.py):

```python
def cmd_done(task_id, output_path='', summary=''):
    if _check_api():
        agent = _infer_agent_id()
        result = _api_post(f'/api/tasks/by-legacy/{task_id}/transition', {
            'new_state': 'done',  # ← TaskState에 'done'은 존재하지 않음
            ...
        })
```

### 결과

`done` 명령 실행 시 모든 호출이 백엔드에서 `Invalid state: done`으로 거부됩니다. 작업이 결코 `Completed` 상태에 도달하지 못합니다.

### 수정 방안

```python
def cmd_done(task_id, output_path='', summary=''):
    if _check_api():
        agent = _infer_agent_id()
        result = _api_post(f'/api/tasks/by-legacy/{task_id}/transition', {
            'new_state': 'Completed',  # PascalCase enum 값
            'agent': agent,
            'reason': summary or '업무가 완료되었습니다',
        })
```

`cmd_block`도 동일하게 점검 필요:

```python
# 현재 (수정 불필요 — 'blocked'는 옵션 B 별칭으로 처리되거나 옵션 A로 'Blocked'로 변경)
'new_state': 'blocked',

# 옵션 A 적용 시
'new_state': 'Blocked',
```

### 추가 점검 포인트

상태 머신 [`STATE_TRANSITIONS`](../edict/backend/app/models/task.py)에 따르면 `Completed`로의 직접 전이는 다음 상태에서만 가능:

```
InProgress    → Completed
FinalReview   → Completed
PendingConfirm → Completed
```

`SejaFinalReview` 또는 `HongmungwanDraft` 상태에서 `cmd_done`을 호출하면 **상태 전이 규칙 위반**으로 다시 400이 떨어집니다. 이 부분은 호출자(에이전트 SOUL.md)가 정상 흐름을 따르도록 가이드해야 하며, 코드 변경 사항은 아닙니다.

---

## 3. 🔴 `agents.json`의 Windows 경로 하드코딩

### 현황

[`agents.json`](../agents.json):

```json
{
  "id": "seja",
  "name": "seja",
  "workspace": "C:\\Users\\<YOUR_USER>\\.openclaw\\workspace-seja",
  "agentDir": "C:\\Users\\<YOUR_USER>\\.openclaw\\agents\\seja\\agent",
  ...
}
```

- 모든 12개 agent 항목에 Windows 경로(`C:\\Users\\<YOUR_USER>\\...`) 하드코딩
- `<YOUR_USER>` 플레이스홀더가 그대로 남아 있음
- macOS / Linux 사용자는 이 파일이 그대로면 동작 안 함

### `install.sh` 자동 치환 여부

`install.sh`가 OS별 경로(`$HOME/.openclaw/...`)로 치환하는 로직이 있어야 정상이지만, 명시적 치환 단계가 보이지 않습니다. (확인 필요 — `install.sh` 내 `sed` 또는 `jq` 호출부)

### 수정 방안

**옵션 A**: `agents.json`을 OS-agnostic 템플릿으로 변경.

```json
{
  "id": "seja",
  "name": "seja",
  "workspace": "${OPENCLAW_HOME}/workspace-seja",
  "agentDir": "${OPENCLAW_HOME}/agents/seja/agent"
}
```

런타임에 `${OPENCLAW_HOME}`을 환경변수로 치환. (`os.path.expandvars` 또는 jq 활용)

**옵션 B**: `install.sh`/`install.ps1`에서 OS별 경로로 치환.

```bash
# install.sh 안에서
OC_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
USER_PLACEHOLDER='<YOUR_USER>'

jq --arg home "$OC_HOME" \
   '.[] |= (.workspace |= sub("C:\\\\Users\\\\<YOUR_USER>\\\\.openclaw"; $home)
                | .agentDir   |= sub("C:\\\\Users\\\\<YOUR_USER>\\\\.openclaw"; $home))' \
   agents.json > agents.json.tmp && mv agents.json.tmp agents.json
```

> **권장**: 옵션 A. 하드코딩 경로는 운영 환경 변경(예: `OPENCLAW_HOME=/srv/openclaw`)마다 재설치를 강요합니다.

### 검증 절차

```bash
# install.sh 실행 후
cat agents.json | jq '.[].workspace'
# 기대 출력 (macOS):
# "/Users/comsy/.openclaw/workspace-seja"
# "/Users/comsy/.openclaw/workspace-hongmungwan"
# ...

# Windows 경로(C:\\)나 <YOUR_USER>가 남아 있으면 치환 실패
grep -c "C:\\\\\\\\\\|<YOUR_USER>" agents.json
# 기대 결과: 0
```

---

## 4. 🟡 `cmd_state`의 `now_text` reason 매핑 점검

### 현황

[`edict/scripts/kanban_update_edict.py:230`](../edict/scripts/kanban_update_edict.py):

```python
'reason': now_text or f'상태 변경: {new_state}',
```

`new_state`가 PascalCase로 그대로 들어오면 사람 읽기 좋은 메시지가 아닙니다 (예: `상태 변경: SeungjeongwonAssigned`).

### 수정 방안 (선택)

`STATE_ORG_MAP`을 활용하여 한국어 부서명으로 표현:

```python
edict_state = _STATE_TO_EDICT.get(new_state, new_state)
human_label = STATE_ORG_MAP.get(new_state, new_state)
result = _api_post(f'/api/tasks/by-legacy/{task_id}/transition', {
    'new_state': edict_state,
    'agent': agent,
    'reason': now_text or f'상태 변경: {human_label}',
})
```

이 항목은 **운영 차단은 아니지만** 1, 2번 수정과 함께 처리하면 자연스럽습니다.

---

## 5. 🔴 회귀 방지 테스트 추가

위 1, 2번을 고친 뒤 동일 결함이 재발하지 않도록 [`tests/backend/test_api_tasks.py`](../tests/backend/test_api_tasks.py)에 통합 테스트를 추가해야 합니다.

```python
class TestLegacyApiStateValues:
    """legacy 라우트가 PascalCase TaskState 값을 받아들이는지 보증."""

    @pytest.mark.parametrize("state_value", [
        "SejaFinalReview", "HongmungwanDraft", "SaganwonFinalReview",
        "SeungjeongwonAssigned", "Ready", "InProgress", "FinalReview",
        "Completed", "Blocked", "Cancelled", "Pending", "PendingConfirm",
    ])
    async def test_all_state_values_are_recognized(self, client, mock_svc, state_value):
        """모든 enum 값이 400을 받지 않아야 함 (404는 허용 — task not found)."""
        resp = await client.post(
            f"/api/tasks/by-legacy/JJC-TEST-001/transition",
            json={"new_state": state_value},
        )
        assert resp.status_code != 400, f"{state_value} 거부됨: {resp.json()}"
```

옵션 B (별칭) 적용 시 추가 테스트:

```python
@pytest.mark.parametrize("alias,canonical", [
    ("seja", "SejaFinalReview"),
    ("hongmungwan", "HongmungwanDraft"),
    ("done", "Completed"),
    ("in_progress", "InProgress"),
])
async def test_legacy_aliases_resolve(self, client, mock_svc, alias, canonical):
    ...
```

---

## 우선순위 및 작업 순서

| 순서 | 항목 | 영향 | 예상 소요 |
|------|------|------|----------|
| 1 | `_STATE_TO_EDICT` PascalCase 변경 | 모든 `state`/`done`/`block` 명령 즉시 복구 | 5분 |
| 2 | `cmd_done`의 `'done'` → `'Completed'` | `done` 명령 복구 | 2분 |
| 3 | 회귀 방지 테스트 추가 | 재발 방지 | 15분 |
| 4 | 백엔드 옵션 B 별칭 (선택) | 구버전 호환성 보강 | 10분 |
| 5 | `agents.json` OS-agnostic 변경 | 멀티플랫폼 설치 정상화 | 30분 |

**총 예상 소요**: 1시간 미만으로 모든 Critical 항목 해결 가능.

---

## 영향 범위 요약

이 문서의 1~3번 항목이 수정되지 않으면:

- ❌ `state`, `done`, `block` 명령 100% 실패
- ❌ Windows가 아닌 환경에서 첫 실행 시 즉시 워크스페이스 누락
- ✅ 작동하는 것: `create`, `flow`, `progress`, `todo` (전이 미사용 명령들)

즉, **에이전트가 작업을 완료할 수 없는 상태**입니다. Harness Orchestrator로서의 핵심 기능이 동작하지 않습니다.
