# 조선식 내부 식별자 마이그레이션 3차 계획

## 1. 문서 목적

이 문서는 `docs/joseon-localization-phase2-plan.md` 이후 진행할 3차 마이그레이션의 기준 문서다.

1차 작업은 사용자 노출면 한글화와 조선식 재해석에 집중했고, 2차 작업은 현대 한국어 재번역과 CLI 문구 한글화를 수행했다. 3차 작업은 **번역이 아닌 내부 식별자 전환**이다.

이번 3차 작업의 목표는 다음과 같다.

- 기존 중국식 내부 ID와 상태 키를 조선식/한국어 체계에 맞는 새 키로 전환한다.
- 코드, 테스트, 문서, 데모 데이터를 새 키 기준으로 정리한다.
- 프로젝트 초기 상태이므로 백업 없이 직접 변경한다.

## 2. 3차 작업 원칙

### 2.1 직접 전환

프로젝트가 아직 사용 전 상태이므로 복잡한 호환 레이어 없이 직접 변경한다.

- 기존 키를 새 키로 전면 교체한다.
- 호환 레이어는 최소화하거나 제거한다.
- 코드와 데이터를 새 키 기준으로 일관되게 유지한다.

### 2.2 단계적 작업

작업 순서를 정하여 체계적으로 변경한다.

1. 1단계: ID/상태 키 매핑 확정
2. 2단계: 백엔드 모델 및 enum 변경
3. 3단계: 프론트엔드 코드 변경
4. 4단계: 대시보드 코드 변경
5. 5단계: 스크립트 파일 변경
6. 6단계: 테스트 코드 변경
7. 7단계: 데모 데이터 및 문서 정리
8. 8단계: 검수 및 확인

## 3. ID/상태 키 매핑 표

### 3.1 Agent ID 매핑

| 기존 ID (Legacy) | 새 ID (New) | 표시명 (Display) | 비고 |
|---|---|---|---|
| `taizi` | `seja` | 세자 | 왕세자 |
| `zhongshu` | `hongmungwan` | 홍문관 | 기획·초안 |
| `menxia` | `saganwon` | 사간원 | 심의·간쟁 |
| `shangshu` | `seungjeongwon` | 승정원 | 배분·조율 |
| `hubu` | `hojo` | 호조 | 자원·데이터 |
| `libu` | `yejo` | 예조 | 문서·형식 |
| `bingbu` | `byeongjo` | 병조 | 구현·기술 |
| `xingbu` | `hyeongjo` | 형조 | 감사·보안 |
| `gongbu` | `gongjo` | 공조 | 배포·운영 |
| `libu_hr` | `ijo` | 이조 | 인사·권한 |
| `zaochao` | `jobocheong` | 조보청 | 브리핑·뉴스 |
| `qintianjian` | `gwansanggam` | 관상감 | 천문·역법 |

### 3.2 상태 키 매핑

| 기존 상태 키 | 새 상태 키 | 표시명 | 설명 |
|---|---|---|---|
| `Pending` | `Pending` | 접수 대기 | 변경 없음 |
| `Taizi` | `SejaFinalReview` | 세자 분류 | 세자 검토 단계 |
| `HongmungwanDraft` | `HongmungwanDraft` | 홍문관 기안 | 홍문관 초안 단계 |
| `Menxia` | `SaganwonFinalReview` | 사간원 심의 | 사간원 검토 단계 |
| `SeungjeongwonAssigned` | `SeungjeongwonAssigned` | 승정원 배분 완료 | 승정원 배분 완료 |
| `Ready` | `Ready` | 집행 대기 | 실행 준비 |
| `InProgress` | `InProgress` | 집행 중 | 실행 중 |
| `Review` | `FinalReview` | 취합 검토 | 최종 검토 |
| `Completed` | `Completed` | 완료 | 완료 |
| `Blocked` | `Blocked` | 중단 | 변경 없음 |
| `Cancelled` | `Cancelled` | 취소 | 변경 없음 |
| `PendingConfirm` | `PendingConfirm` | 확인 대기 | 변경 없음 |

## 4. 코드 변경 지침

### 4.1 변경 대상 파일

**백엔드 소스 코드:**
- `edict/backend/app/models/task.py` - TaskStatus enum
- `edict/backend/app/models/event.py` - Event 관련 모델
- `edict/backend/app/models/thought.py` - Thought 모델
- `edict/backend/app/models/todo.py` - Todo 모델
- `edict/backend/app/models/audit.py` - Audit 모델
- `edict/backend/app/models/outbox.py` - Outbox 모델
- `edict/backend/app/api/*.py` - API 엔드포인트 내 하드코딩된 키
- `edict/backend/app/workers/*.py` - 워커 상태 전이 로직 내 키
- `edict/backend/app/services/*.py` - 서비스 레이어 내 키
- `edict/backend/app/channels/*.py` - 채널 모듈 내 키

**프론트엔드 소스 코드:**
- `edict/frontend/src/store.ts` - 상태 관리 스토어 내 하드코딩된 키
- `edict/frontend/src/api.ts` - API 호출 시 하드코딩된 키
- `edict/frontend/src/components/*.tsx` - UI 컴포넌트 내 키
- `edict/frontend/src/components/*.ts` - UI 컴포넌트 내 키
- `edict/frontend/src/compat/` - 호환 레이어 (필요시 최소화)

**대시보드 소스 코드:**
- `dashboard/server.py` - 대시보드 서버 내 하드코딩된 키
- `dashboard/court_discuss.py` - 법원 토론 모듈 내 키
- `dashboard/dashboard.html` - 레거시 HTML 내 키
- `dashboard/auth.py` - 인증 모듈 내 키

**스크립트 파일:**
- `scripts/*.py` - `kanban_update.py`, `skill_manager.py`, `sync_agent_config.py` 등
- `scripts/*.sh` - bash 스크립트
- `scripts/*.ps1` - PowerShell 스크립트
- `./*.sh` - 루트 디렉토리 쉘 스크립트 (`edict.sh`, `install.sh`, `uninstall.sh`, `start.sh`, `run_loop.sh` 등)
- `./*.ps1` - 루트 디렉토리 PowerShell 스크립트 (`install.ps1`)
- `edict/scripts/*.py` - `kanban_update_edict.py` 등

**테스트 코드:**
- `tests/*.py` - 테스트 파일 내 하드코딩된 키
- `edict/backend/app/tests/*.py` (있는 경우) - 백엔드 테스트 내 키

**데모 데이터:**
- `docker/demo_data/*.json` - 데모 데이터 파일

### 4.2 변경 방법

1. **Agent ID 변경**: 기존 중국식 ID(`taizi`, `zhongshu` 등)를 새 ID(`seja`, `hongmungwan` 등)로 직접 교체
2. **상태 키 변경**: 기존 상태 키(`Taizi`, `Menxia`, `Review` 등)를 새 상태 키(`SejaFinalReview`, `SaganwonFinalReview`, `FinalReview` 등)로 직접 교체
3. **표시명 확인**: UI에 표시되는 명칭이 올바른 조선식 명칭인지 확인
4. **import 경로**: compat 모듈 사용 시 import 경로 정리

## 5. DB 스키마 설정

### 5.1 초기 스키마

프로젝트가 사용 전 상태이므로, 초기 DB 스키마를 새 키 기준으로 설정한다.

- `edict/backend/app/models/task.py`: TaskStatus enum을 새 키로 정의
- `edict/migration/versions/001_initial.py`: 초기 마이그레이션을 새 키 기준으로 작성
- 추가 마이그레이션이 필요한 경우 `edict/migration/versions/002_*.py` 생성

### 5.2 Alembic 마이그레이션

```python
# edict/migration/versions/001_initial.py (수정 또는 재작성)

from alembic import op
import sqlalchemy as sa

# 새 키 기준 TaskStatus enum
task_status_enum = sa.Enum(
    'Pending',
    'SejaFinalReview',
    'HongmungwanDraft',
    'SaganwonFinalReview',
    'SeungjeongwonAssigned',
    'Ready',
    'InProgress',
    'FinalReview',
    'Completed',
    'Blocked',
    'Cancelled',
    'PendingConfirm',
    name='taskstatus'
)

op.create_table(
    'tasks',
    # ... 컬럼 정의
    sa.Column('status', task_status_enum, nullable=False),
    # ...
)
```

## 6. 데모 데이터 설정

### 6.1 JSON 데이터

데모 데이터를 새 키 기준으로 작성한다.

- `docker/demo_data/agent_config.json`: Agent ID를 새 키로 설정
- `docker/demo_data/live_status.json`: 상태 키를 새 키로 설정
- `docker/demo_data/officials_stats.json`: Agent ID를 새 키로 설정
- 기타 `docker/demo_data/*.json` 파일들

### 6.2 변환 스크립트 (참고용)

초기 데이터 설정을 위해 참고할 수 있는 스크립트 구조 (실제 실행보다는 새 데이터 작성 권장).

```python
# scripts/setup_demo_data.py 예시 구조

import json

AGENT_ID_MAPPING = {
    "taizi": "seja",
    "zhongshu": "hongmungwan",
    # ... 나머지 매핑
}

STATUS_KEY_MAPPING = {
    "Taizi": "SejaFinalReview",
    "HongmungwanDraft": "HongmungwanDraft",
    # ... 나머지 매핑
}

def convert_json_file(filepath):
    """JSON 파일 내 ID와 상태 키를 새 키로 변환"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 변환 로직
    # ...
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

## 7. 실행 순서

### 7.1 1단계: ID/상태 키 매핑 확정

- 매핑 표 최종 검토
- 표시명 확인
- 변경 대상 파일 목록 정리

### 7.2 2단계: 백엔드 모델 및 enum 변경

- `edict/backend/app/models/task.py` - TaskStatus enum을 새 키로 업데이트
- `edict/backend/app/models/event.py` - Event 관련 모델 업데이트
- `edict/backend/app/models/thought.py` - Thought 모델 업데이트
- `edict/backend/app/models/todo.py` - Todo 모델 업데이트
- `edict/backend/app/models/audit.py` - Audit 모델 업데이트
- `edict/backend/app/models/outbox.py` - Outbox 모델 업데이트

### 7.3 3단계: 백엔드 로직 변경

- `edict/backend/app/workers/*.py` - workers의 상태 전이 로직 내 하드코딩된 키 수정
- `edict/backend/app/api/*.py` - API 엔드포인트 내 하드코딩된 키 수정
- `edict/backend/app/services/*.py` - 서비스 레이어 내 하드코딩된 키 수정
- `edict/backend/app/channels/*.py` - 채널 모듈 내 하드코딩된 키 수정

### 7.4 4단계: 프론트엔드 코드 변경

- `edict/frontend/src/store.ts` - 상태 관리 스토어 내 하드코딩된 키 수정
- `edict/frontend/src/api.ts` - API 호출 시 하드코딩된 키 수정
- `edict/frontend/src/components/*.tsx`, `*.ts` - UI 컴포넌트 내 하드코딩된 키 수정
- `edict/frontend/src/compat/` - compat 모듈 정리 (필요시)
- UI 표시명 최종 확인

### 7.5 5단계: 대시보드 소스 코드 변경

- `dashboard/server.py` - 대시보드 서버 내 하드코딩된 키 수정
- `dashboard/court_discuss.py` - 법원 토론 모듈 내 하드코딩된 키 수정
- `dashboard/dashboard.html` - 레거시 HTML 내 하드코딩된 키 수정
- `dashboard/auth.py` - 인증 모듈 내 키 수정

### 7.6 6단계: 스크립트 파일 변경

- `scripts/*.py` 내 agent ID, 상태 키 하드코딩 부분 변환
- `scripts/*.sh`, `scripts/*.ps1` 내 하드코딩된 키 변환
- 루트 디렉토리 `./*.sh` (edict.sh, install.sh 등) 변환
- 루트 디렉토리 `./*.ps1` (install.ps1 등) 변환
- `edict/scripts/*.py` (kanban_update_edict.py 등) 변환
- 스크립트 실행 테스트로 정상 동작 확인

### 7.7 7단계: 테스트 코드 변경

- `tests/*.py` - 테스트 파일 내 하드코딩된 키 수정
- `edict/backend/app/tests/*.py` (있는 경우) - 백엔드 테스트 내 키 수정
- 테스트 케이스의 키 참조 업데이트
- 테스트 실행으로 정상 동작 확인

### 7.8 8단계: 데모 데이터 및 문서 정리

- `docker/demo_data/*.json` - 데모 데이터를 새 키 기준으로 작성/수정
- `docs/` - 관련 문서 내 키 참조 업데이트
- `README.md` - 필요시 업데이트
- 스크린샷 갱신 필요 여부 확인

### 7.9 9단계: 검수 및 확인

- 단위 테스트 실행
- 통합 테스트 실행
- 수동 검수 수행
- 버그 수정

## 8. 검수 기준

### 8.1 기능 검수

- 새 키로 API 호출 시 정상 응답
- 상태 전이 로직이 깨지지 않음
- UI의 모든 표시명이 올바른 조선식 명칭인가?

### 8.2 코드 검수

**백엔드/프론트엔드:**
- 하드코딩된 기존 키가 남아있지 않음
- 모든 키 참조가 새 키를 사용함
- 테스트 코드가 새 키를 기준으로 업데이트됨

**스크립트 파일:**
- `scripts/*.py` 내 하드코딩된 기존 키가 새 키로 변환됨
- `scripts/*.sh`, `scripts/*.ps1` 내 하드코딩된 키가 변환됨
- 루트 디렉토리 `./*.sh`, `./*.ps1` 내 키가 변환됨
- `edict/scripts/*.py` 내 키가 변환됨
- 모든 스크립트가 새 키에서 정상 동작함

**테스트 코드:**
- `tests/*.py` 내 하드코딩된 기존 키가 새 키로 변환됨
- `edict/backend/app/tests/*.py` (있는 경우) 내 키가 변환됨
- 모든 테스트 케이스가 새 키를 기준으로 업데이트됨
- 테스트 실행 시 정상 동작함

**데모 데이터:**
- `docker/demo_data/*.json` 내 모든 ID와 상태 키가 새 키로 설정됨
- 데모 데이터가 정상 렌더링되는가?

### 8.3 수동 검수 항목

- [ ] 모든 agent ID가 새 키로 변환되었는가?
- [ ] 상태 키가 새 키로 표시되는가?
- [ ] UI의 모든 표시명이 올바른가?
- [ ] 데모 데이터가 정상 렌더링되는가?
- [ ] 스크린샷 갱신 필요 여부 확인
- [ ] `scripts/*.py` 내 하드코딩된 agent ID와 상태 키가 변환되었는가?
- [ ] `scripts/*.sh` 내 하드코딩된 키가 변환되었는가?
- [ ] `scripts/*.ps1` 내 하드코딩된 키가 변환되었는가?
- [ ] 루트 디렉토리의 `./*.sh` (edict.sh, install.sh 등)가 변환되었는가?
- [ ] `edict/scripts/*.py` 내 키가 변환되었는가?
- [ ] 스크립트 실행 시 새 키로 정상 동작하는가?

## 9. 결정 사항 요약

- 3차는 번역이 아닌 내부 식별자 전환 작업이다.
- Agent ID는 음차 방식으로 변경 (taizi → seja, zhongshu → hongmungwan 등)
- 상태 키는 조선식 역할명으로 변경 (Taizi → SejaFinalReview, Menxia → SaganwonFinalReview 등)
- 프로젝트가 사용 전 상태이므로 백업 없이 직접 변경한다.
- 복잡한 호환 레이어 대신 직접 전환 방식을 취한다.
- DB 스키마는 초기 설정부터 새 키 기준으로 작성한다.
- 데모 데이터도 새 키 기준으로 작성/수정한다.
- **프로젝트 전체 소스 코드 변경 대상 포함**
  - 백엔드: `edict/backend/app/` 하위 모든 소스 코드 (models, api, workers, services, channels)
  - 프론트엔드: `edict/frontend/src/` 하위 모든 소스 코드 (store.ts, api.ts, components)
  - 대시보드: `dashboard/` 하위 소스 코드 (server.py, court_discuss.py, dashboard.html)
  - 스크립트: `scripts/*.*`, `./*.sh`, `./*.ps1`, `edict/scripts/*.py`
  - 테스트: `tests/*.py`, `edict/backend/app/tests/*.py`
  - JSON 데이터: `docker/demo_data/*.json`
  - 쉘 스크립트 내 하드코딩된 agent ID와 상태 키 변환
  - 루트 디렉토리 쉘 스크립트(edict.sh, install.sh 등) 변환

## 10. 참고 문서

**계획 문서:**
- `docs/joseon-localization-plan.md` - 1차 현지화 계획
- `docs/joseon-localization-phase2-plan.md` - 2차 현대어 재번역 계획
- `docs/task-dispatch-architecture.md` - 작업 분배 아키텍처

**백엔드 소스 코드:**
- `edict/backend/app/models/task.py` - Task 모델 및 TaskStatus enum 정의
- `edict/backend/app/models/event.py` - Event 모델 정의
- `edict/backend/app/workers/*.py` - 워커 상태 전이 로직
- `edict/backend/app/api/*.py` - API 엔드포인트

**프론트엔드 소스 코드:**
- `edict/frontend/src/store.ts` - 상태 관리 스토어
- `edict/frontend/src/api.ts` - API 호출
- `edict/frontend/src/components/*.tsx` - UI 컴포넌트

**대시보드 소스 코드:**
- `dashboard/server.py` - 대시보드 서버
- `dashboard/court_discuss.py` - 조조 토론 모듈
- `dashboard/dashboard.html` - 레거시 HTML
- `dashboard/auth.py` - 인증 모듈

**마이그레이션 스크립트:**
- `edict/migration/env.py` - 마이그레이션 환경 설정
- `edict/migration/migrate_json_to_pg.py` - JSON to PostgreSQL 마이그레이션
- `edict/migration/versions/*.py` - 기존 마이그레이션 파일들

**스크립트 파일:**
- `scripts/kanban_update.py` - 칸반 업데이트 CLI
- `scripts/skill_manager.py` - 스킬 관리 CLI
- `scripts/*.sh`, `scripts/*.ps1` - 보조 스크립트
- `./*.sh`, `./*.ps1` - 루트 디렉토리 스크립트

**테스트 코드:**
- `tests/*.py` - 테스트 파일
- `edict/backend/app/tests/*.py` - 백엔드 테스트 (있는 경우)

**데모 데이터:**
- `docker/demo_data/*.json` - 데모 데이터 파일
