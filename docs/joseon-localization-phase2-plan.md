# 조선식 한글화 2차 번역 계획

## 1. 문서 목적

이 문서는 `docs/joseon-localization-plan.md` 이후 진행할 2차 번역의 기준 문서다.

1차 작업은 사용자에게 보이는 큰 표면을 조선식 한국어 체계로 바꾸는 데 집중했다. 2차 작업은 그 다음 단계로, 남아 있는 어려운 한자어와 CLI 사용자 노출 문구를 현대 한국어 기준으로 정리한다.

이번 2차 작업의 목표는 다음과 같다.

- 1차 번역에 남은 한자 병기와 어려운 한자어를 현대 한국어로 바꾼다.
- `scripts/kanban_update.py`, `scripts/skill_manager.py`의 사용자 노출 CLI 문구를 한국어로 통일한다.
- 기존 중국어 입력 접두사와 과거 데이터는 계속 인식하되, 새로 표시되는 문구는 한국어 기준으로 정규화한다.
- 내부 agent ID, 상태 키, 워크스페이스 경로, JSON 키는 변경하지 않는다.

## 2. 2차 작업 원칙

### 2.1 현대 한국어 우선

사용자가 뜻을 바로 알기 어려운 표현은 현대 한국어로 바꾼다.

- `하지(下旨)`처럼 한자 병기가 붙은 표현은 뜻 중심으로 바꾼다.
- `회보`, `상신`, `회보각`처럼 한국어로 쓰였지만 의미가 낯선 표현도 더 쉬운 말로 정리한다.
- 의미가 모호해질 경우 단어 하나만 치환하지 않고 짧은 설명형 표현을 허용한다.

### 2.2 기관명과 직위명 유지

조선식 세계관의 핵심 정체성을 이루는 기관명과 직위명은 유지한다.

- 유지 대상: `세자`, `홍문관`, `사간원`, `승정원`, `호조`, `예조`, `병조`, `형조`, `공조`, `이조`, `조보청`, `관상감`
- 유지 이유: 1차 작업에서 이미 사용자 노출 체계와 agent 역할 설명의 기준 명칭으로 정리되었다.
- 단, 기관 설명 문장 안의 어려운 행위 표현은 현대 한국어로 바꿀 수 있다.

### 2.3 과거 입력 호환 유지

기존 데이터와 외부 런타임에서 들어올 수 있는 중국어 표현은 계속 인식한다.

- `传旨`, `下旨`, `傳旨` 접두사는 계속 정규화 대상이다.
- 기존 JSON 데이터에 남아 있는 과거 문자열은 2차에서 사용자 노출 문맥을 기준으로 정리한다.
- 정규화 결과로 새로 저장되거나 표시되는 기본 문구는 한국어를 사용한다.

### 2.4 내부 식별자 변경 금지

2차에서는 다음 항목을 변경하지 않는다.

- agent ID: `taizi`, `zhongshu`, `menxia`, `shangshu`, `hubu`, `libu`, `bingbu`, `xingbu`, `gongbu`, `libu_hr`, `zaochao`
- 상태 키: `Pending`, `Taizi`, `Zhongshu`, `Menxia`, `Assigned`, `Next`, `Doing`, `Review`, `Done`, `Blocked`, `Cancelled`, `PendingConfirm`
- 디렉터리명, 워크스페이스 경로명, 세션 키, JSON 키, DB enum
- 테스트에서 내부 식별자로 검증하는 값

이 항목들은 3차 마이그레이션에서 별도 설계 후 다룬다.

## 3. 용어 변환 기준

### 3.1 어명·결재·보고 계열

| 기존 표기 | 2차 표기 | 적용 기준 |
|---|---|---|
| `하지(下旨)` | 어명 하달 | 임금의 지시가 내려오는 행위 |
| `전지(傳旨)` / `전지(传旨)` | 어명 전달 | 지시를 다음 단계로 넘기는 행위 |
| `어비(御批)` | 임금 결재 | 최종 승인 또는 결재 |
| `전보(轉報)` / `전보(转报)` | 보고 전달 | 결과나 상황을 전달하는 행위 |
| `지시(旨意)` | 지시 | 한자 병기 제거 |
| `유전(流轉)` | 흐름 | 상태나 업무 이동 설명 |
| `천하요문(天下要闻)` | 주요 뉴스 | 조보/브리핑 화면의 뉴스 명칭 |

### 3.2 직무 설명의 어려운 한자어

| 위치 | 기존 표기 | 2차 표기 |
|---|---|---|
| `agents/libu/SOUL.md` | 전장(典章)과 의제(儀制) | 법령과 의례 제도 |
| `agents/libu_hr/SOUL.md` | 전선(銓選) | 인사 선발 |
| `agents/zaochao/SOUL.md` | 도문병모(圖文倂茂)의 간보(簡報) | 그림과 글이 어우러진 브리핑 |

`agents/qintianjian/SOUL.md`의 `감정(監正)`은 직위명 성격이 강하므로 2차에서는 보존한다.

### 3.3 단독 한자어성 표현

| 기존 표기 | 2차 표기 | 적용 기준 |
|---|---|---|
| `회보` | 결과 보고 | 사용자가 최종 산출물을 받는 문맥 |
| `상신` | 상위 보고 | 위 단계로 결과를 올리는 문맥 |
| `회보각` | 결과 보고함 | 완료 결과 보관 UI 패널 |
| `어명 라이브러리` | 어명 템플릿 | 명령 예시/템플릿 모음 |
| `어명 템플릿` | 어명 템플릿 | 이미 자연스러운 곳은 유지 |
| `간쟁` | 직언/조언 | 사간원 검토·지적 역할 설명 |
| `조정` | 조정 | 현대 한국어에서도 자연스러우므로 유지 |

`군기처`는 UI 정체성이 강하므로 2차에서 보존한다. 다만 설명 문구에서는 `작업 통제실`, `실시간 칸반`, `진행 관리 화면` 같은 쉬운 설명을 덧붙일 수 있다.

## 4. 대상 파일군

### 4.1 현대어 재번역 대상

- `README.md`
- `docs/getting-started.md`
- `docs/task-dispatch-architecture.md`
- `docs/remote-skills-guide.md`
- `docs/remote-skills-quickstart.md`
- `examples/*.md`
- `agents/GLOBAL.md`
- `agents/*/SOUL.md`
- `agents/groups/*.md`
- `dashboard/server.py`
- `dashboard/court_discuss.py`
- `dashboard/dashboard.html`
- `edict/frontend/src/*`
- `data/schema.json`
- `docker/demo_data/*.json`

### 4.2 CLI 사용자 노출 문구 대상

- `scripts/kanban_update.py`
  - help/docstring 사용 예시
  - stdout/stderr 메시지
  - logging 메시지 중 사용자가 터미널에서 직접 보는 문구
  - 기본 remark/now 문구
  - `state`, `flow`, `progress`, `done`, `block`, `confirm`, `todo` 관련 안내 문구
- `scripts/skill_manager.py`
  - argparse 설명과 help 문구
  - `add-remote`, `list-remote`, `update-remote`, `remove-remote`, `import-official-hub`, `check-updates` 출력
  - 다운로드 실패, 재시도, 네트워크 안내, 성공/실패 요약 문구

### 4.3 선택 대상

다음 파일은 사용자 노출 가능성이 낮으므로 2차 필수 범위는 아니다. 다만 작업 중 같은 문맥을 건드릴 경우 주석과 보조 문구를 한국어로 정리할 수 있다.

- `scripts/*.sh`
- `scripts/*.ps1`
- `scripts/refresh_watcher.py`
- `scripts/sync_from_openclaw_runtime.py`
- `edict/scripts/kanban_update_edict.py`
- `dashboard/auth.py`

## 5. 실행 순서

### 5.1 1단계: 용어 검색과 적용 목록 확정

다음 키워드로 현재 잔여 표기를 확인한다.

```bash
rg -n "하지\\(下旨\\)|전지\\(傳旨\\)|전지\\(传旨\\)|어비\\(御批\\)|전보\\(轉報\\)|전보\\(转报\\)|지시\\(旨意\\)|유전\\(流轉\\)|천하요문\\(天下要闻\\)|회보각|회보|상신|간쟁|传旨|下旨" README.md docs examples agents dashboard edict/frontend/src data docker scripts
```

검색 결과는 모두 기계적으로 치환하지 않는다. 사용자에게 보이는 문장, UI 라벨, CLI 출력, 데모 데이터 문맥을 우선 적용한다.

### 5.2 2단계: 문서와 agent 설명 현대어화

제품 문서와 agent 문서의 어려운 표현을 먼저 정리한다.

- 문서 제목과 섹션명은 사용자가 바로 이해할 수 있게 바꾼다.
- agent 역할 설명은 조선식 세계관을 유지하되 과도한 한자 병기를 제거한다.
- 예시 명령과 상태 키는 내부 호환을 위해 그대로 둔다.

### 5.3 3단계: UI와 데모 데이터 현대어화

프론트엔드, 레거시 대시보드, 데모 JSON의 노출 문자열을 정리한다.

- UI 탭명과 버튼명은 짧고 명확하게 유지한다.
- 완료 결과 보관 영역은 `결과 보고` 계열로 통일한다.
- 기존 데이터의 `agent:<id>:...`, `workspace-<id>` 같은 내부 키는 바꾸지 않는다.

### 5.4 4단계: CLI 사용자 문구 한글화

`scripts/kanban_update.py`와 `scripts/skill_manager.py`의 사용자 노출 문구를 한국어로 정리한다.

- 명령 이름과 인자 이름은 유지한다.
- 내부 상태 키와 agent ID는 유지한다.
- 사용자가 터미널에서 읽는 성공/실패/재시도/권한 거부/검증 실패 메시지를 한국어로 바꾼다.
- 기존 `传旨/下旨` 입력 정규화는 유지하되, 기본 생성 문구는 `어명 하달`, `지시 접수`, `결과 보고` 같은 표현으로 바꾼다.

### 5.5 5단계: 검수와 잔여 목록 기록

2차 범위 안에서 남겨도 되는 표현과 반드시 바꿔야 하는 표현을 분리한다.

- 내부 ID나 상태 키로 남은 문자열은 잔여 번역 실패로 보지 않는다.
- 외부 서비스명 `Feishu(飞书)`, `WeCom(企业微信)`은 유지할 수 있다.
- 코드 주석에 남은 중국어는 사용자 노출 문구가 아니면 3차 전 별도 정리 후보로 남긴다.

## 6. 검수 기준

### 6.1 문자열 검수

- 3장의 변환 표가 대상 파일군에 일관되게 적용되었다.
- 같은 개념이 `회보`, `상신`, `결과 보고`로 섞여 사용자에게 노출되지 않는다.
- `传旨/下旨`는 입력 호환 정규식으로만 남고, 새 안내 문구의 기본 표현은 한국어다.
- 기관명과 직위명은 1차 기준과 충돌하지 않는다.

### 6.2 호환성 검수

- 내부 agent ID와 상태 키는 그대로 유지된다.
- `kanban_update.py`의 상태 전이 검증이 깨지지 않는다.
- `skill_manager.py`의 원격 skill 추가/목록/갱신/삭제 명령 이름은 바뀌지 않는다.
- 기존 JSON 데모 데이터가 문법 오류 없이 로드된다.

### 6.3 실행 검수

Python 변경 후 다음 명령을 실행한다.

```bash
python3 -m py_compile dashboard/server.py dashboard/court_discuss.py scripts/kanban_update.py scripts/skill_manager.py
```

JSON 변경 후 다음 명령을 실행한다.

```bash
jq empty data/schema.json docker/demo_data/*.json
```

CLI help 출력은 다음 명령으로 확인한다.

```bash
python3 scripts/kanban_update.py
python3 scripts/skill_manager.py --help
```

## 7. 3차 작업 예고

3차 작업은 번역 작업이 아니라 `호환성 있는 내부 식별자 전환`이다. 2차가 사용자 노출 문구를 정리하는 작업이라면, 3차는 런타임 내부 키와 저장 데이터를 바꾸는 마이그레이션 작업이다.

### 7.1 3차 작업의 목표

- 기존 중국식 내부 ID와 상태 키를 조선식/한국어 체계에 맞는 새 키로 전환한다.
- 기존 데이터와 외부 OpenClaw 런타임이 깨지지 않도록 양방향 호환 레이어를 둔다.
- 새 키 기준으로 코드, 테스트, 문서, 데모 데이터를 정리한다.

### 7.2 3차 대상

- agent ID
  - 예: `taizi` → `seja`
  - 예: `zhongshu` → `hongmungwan`
  - 예: `menxia` → `saganwon`
- 상태 키
  - 예: `Taizi`, `Zhongshu`, `Menxia`, `Assigned` 같은 상태 키의 새 이름 검토
- 워크스페이스와 세션 키
  - 예: `workspace-zhongshu`
  - 예: `agent:zhongshu:main`
- JSON 데이터와 DB 데이터
  - `data/*.json`
  - `docker/demo_data/*.json`
  - backend migration 대상 데이터
- 라우팅과 enum
  - `edict/backend/app/models/task.py`
  - `edict/backend/app/workers/*`
  - `dashboard/server.py`
  - `scripts/kanban_update.py`
- 테스트
  - 상태 전이 테스트
  - 대시보드 dispatch 테스트
  - 기존 JSON 기반 E2E 테스트

### 7.3 3차 실행 전 필수 문서

3차를 실행하기 전 별도 문서 `docs/joseon-localization-phase3-migration-plan.md`를 작성해야 한다.

그 문서에는 최소한 다음 내용이 포함되어야 한다.

- 기존 ID와 새 ID의 양방향 매핑 표
- 기존 상태 키와 새 상태 키의 양방향 매핑 표
- 읽기 호환, 쓰기 호환, 표시 호환의 우선순위
- 기존 JSON 데이터 자동 변환기 설계
- DB/백엔드 enum 마이그레이션 방식
- OpenClaw 외부 런타임과 워크스페이스 경로 호환 방식
- 롤백 전략
- 테스트 순서와 수동 검수 절차

### 7.4 3차에서 주의할 점

- 3차는 단순 검색/치환으로 진행하면 안 된다.
- 먼저 alias/compat layer를 만들고, 기존 키와 새 키가 동시에 동작하는 기간을 둔다.
- 저장 데이터 변환은 백업 파일 생성 후 수행한다.
- 기존 session key와 workspace 경로는 외부 런타임과 연결될 수 있으므로 즉시 삭제하지 않는다.
- 3차가 끝나기 전까지 문서에는 기존 키와 새 키의 관계를 함께 설명한다.

## 8. 결정 사항 요약

- 2차는 현대 한국어 재번역과 CLI 사용자 노출 문구 한글화에 집중한다.
- 2차에서는 내부 agent ID, 상태 키, 디렉터리명, JSON 키를 변경하지 않는다.
- 3차는 별도 마이그레이션 작업으로 분리한다.
- 3차 실행 전 `docs/joseon-localization-phase3-migration-plan.md`를 반드시 먼저 작성한다.
- 2차 완료 후에도 내부 키가 영어/중국식으로 남아 있는 것은 의도된 호환성 유지다.
