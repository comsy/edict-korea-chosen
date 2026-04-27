<h1 align="center">⚔️ 3사6조 · Edict</h1>

<p align="center">
  <strong>1300년 전 제국 통치 체계로 AI 멀티 에이전트 협업 아키텍처를 다시 설계했습니다.<br>그 결과, 옛 사람들이 현대 AI 프레임워크보다 분권과 견제를 더 잘 이해하고 있었음이 드러났습니다.</strong>
</p>

<p align="center">
  <sub>12개 AI Agent (업무 역할 11 + 호환 역할 1) 가 3사6조를 구성합니다: 세자 분류, 홍문관 기획, 사간원 심의/반려, 승정원 배분, 6조 + 이조 병렬 집행.<br>CrewAI 보다 <b>제도적 심의</b> 한 층, AutoGen 보다 <b>실시간 칸반</b> 하나가 더 있습니다.</sub>
</p>

<p align="center">
  <a href="#-demo">🎬 Demo</a> ·
  <a href="#-30초-빠른-체험">🚀 30초 체험</a> ·
  <a href="#-아키텍처">🏛️ 아키텍처</a> ·
  <a href="#-기능-전경">📋 칸반 기능</a> ·
  <a href="docs/task-dispatch-architecture.md">📚 아키텍처 문서</a> ·
  <a href="docs/joseon-localization-plan.md">📜 한글화 계획</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/OpenClaw-Required-blue?style=flat-square" alt="OpenClaw">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Agents-12_Specialized-8B5CF6?style=flat-square" alt="Agents">
  <img src="https://img.shields.io/badge/Dashboard-Real--time-F59E0B?style=flat-square" alt="Dashboard">
  <img src="https://img.shields.io/badge/License-MIT-22C55E?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Frontend-React_18-61DAFB?style=flat-square&logo=react&logoColor=white" alt="React">
  <img src="https://img.shields.io/badge/Backend-stdlib_only-EC4899?style=flat-square" alt="Zero Backend Dependencies">
</p>

---

## 🎬 Demo

<p align="center">
  <video src="docs/Agent_video_Pippit_20260225121727.mp4" width="100%" autoplay muted loop playsinline controls>
    브라우저가 비디오 재생을 지원하지 않습니다. 아래 GIF를 보거나 <a href="docs/Agent_video_Pippit_20260225121727.mp4">비디오를 다운로드</a>하세요.
  </video>
  <br>
  <sub>🎥 3사6조 AI 멀티 Agent 협업 전 과정 시연</sub>
</p>

<details>
<summary>📸 GIF 미리보기 (빠른 로딩)</summary>
<p align="center">
  <img src="docs/demo.gif" alt="3사6조 Demo" width="100%">
  <br>
  <sub>Feishu 하지 → 세자 분류 → 홍문관 기획 → 사간원 심의 → 6조 병렬 집행 → 회보 (30초)</sub>
</p>
</details>

> 🐳 **OpenClaw 가 없나요?** `docker run -p 7891:7891 cft0808/edict` 한 줄로 완전한 칸반 Demo (사전 모의 데이터 포함) 를 체험할 수 있습니다.

---

## 🤔 왜 3사6조인가?

대부분의 멀티 Agent 프레임워크의 패턴은 다음과 같습니다:

> *"자, 너희 AI 들끼리 알아서 얘기해보고, 끝나면 결과만 줘."*

그렇게 받은 결과는 어떤 처리를 거쳤는지 알 수 없고, 재현도, 감사도, 개입도 불가능합니다.

**3사6조의 발상은 완전히 다릅니다** —— 한반도/중화권에서 1400년간 작동했던 통치 아키텍처를 그대로 차용했습니다:

```
당신 (임금) → 세자 (분류) → 홍문관 (기획) → 사간원 (심의) → 승정원 (배분) → 6조 (집행) → 회보
```

이는 화려한 메타포가 아니라, **진짜 분권 견제** 입니다:

| | CrewAI | MetaGPT | AutoGen | **3사6조** |
|---|:---:|:---:|:---:|:---:|
| **심의 메커니즘** | ❌ 없음 | ⚠️ 선택 | ⚠️ Human-in-loop | **✅ 사간원 전담 심의 · 반려 가능** |
| **실시간 칸반** | ❌ | ❌ | ❌ | **✅ 군기처 Kanban + 타임라인** |
| **작업 개입** | ❌ | ❌ | ❌ | **✅ 중지 / 취소 / 재개** |
| **흐름 감사** | ⚠️ | ⚠️ | ❌ | **✅ 완전한 회보 보관** |
| **Agent 헬스 모니터링** | ❌ | ❌ | ❌ | **✅ 하트비트 + 활동도 감지** |
| **모델 핫스왑** | ❌ | ❌ | ❌ | **✅ 칸반에서 LLM 원클릭 전환** |
| **스킬 관리** | ❌ | ❌ | ❌ | **✅ Skills 보기 / 추가** |
| **뉴스 집계 푸시** | ❌ | ❌ | ❌ | **✅ 천하요문 + Feishu 푸시** |
| **배포 난이도** | 중 | 고 | 중 | **저 · 원클릭 설치 / Docker** |

> **핵심 차이: 제도적 심의 + 완전한 관측 가능성 + 실시간 개입**

<details>
<summary><b>🔍 왜 「사간원 심의」가 필살기인가? (펼치기)</b></summary>

<br>

CrewAI 와 AutoGen 의 Agent 협업 모드는 **"끝나면 바로 제출"** —— 누구도 산출물 품질을 검토하지 않습니다. QA 부서 없는 회사에서 엔지니어가 코드를 쓰자마자 바로 배포하는 것과 같습니다.

3사6조의 **사간원** 은 바로 이 일을 전담합니다:

- 📋 **방안 품질 심사** —— 홍문관의 기획이 충분히 완전한가? 하위 작업 분해는 합리적인가?
- 🚫 **부적합 산출물 반려** —— warning 이 아니라 곧장 되돌려 다시 하게 함
- 🔄 **재작업 강제 루프** —— 방안이 기준에 도달할 때까지 통과시키지 않음

이것은 선택적 플러그인이 아니라 — **아키텍처의 일부** 입니다. 모든 지시는 반드시 사간원을 거쳐야 하며 예외가 없습니다.

이 때문에 3사6조는 복잡한 작업을 다루어도 결과가 신뢰할 만합니다. 집행 계층으로 보내지기 전에 강제 품질 관문이 있기 때문입니다. 1300년 전 당 태종이 이미 깨달았던 이치 — **견제받지 않는 권력은 반드시 잘못된다.**

</details>

---

## ✨ 기능 전경

### 🏛️ 12부제 Agent 아키텍처
- **세자** 메시지 분류 —— 잡담은 자동 회신, 지시여야 작업 생성
- **3사** (홍문관·사간원·승정원) 가 기획·심의·배분 담당
- **7조** (호·예·병·형·공·이 + 조보관) 가 전문 집행 담당
- 엄격한 권한 매트릭스 —— 누가 누구에게 메시지 보낼 수 있는지 명문화
- **상태 전이 검증** —— `kanban_update.py` 가 합법 전이 경로를 강제, 비정상 점프 거부
- 각 Agent 마다 독립 Workspace · 독립 Skills · 독립 모델
- **지시 데이터 정제** —— 제목/비고에서 파일 경로, 메타데이터, 무효 접두어 자동 제거

### 📋 군기처 칸반 (10개 기능 패널)

<table>
<tr><td width="50%">

**📋 지시 칸반 · Kanban**
- 상태별 컬럼으로 전체 작업 표시
- 부서 필터 + 전문 검색
- 하트비트 뱃지 (🟢활성 🟡정체 🔴경고)
- 작업 상세 + 완전 흐름 체인
- 중지 / 취소 / 재개 조작

</td><td width="50%">

**🔭 부서 모니터 · Monitor**
- 각 상태 작업 수 시각화
- 부서별 분포 가로 막대 그래프
- Agent 헬스 상태 실시간 카드

</td></tr>
<tr><td>

**📜 회보각 · Memorials**
- 완료된 지시는 회보로 자동 보관
- 5단계 타임라인: 어명→홍문관→사간원→6조→회보
- Markdown 으로 원클릭 복사
- 상태 필터링

</td><td>

**📜 어명 라이브러리 · Template Library**
- 9개 사전 설정 어명 템플릿
- 카테고리 필터 · 매개변수 폼 · 예상 시간 및 비용
- 지시 미리보기 → 원클릭 하지

</td></tr>
<tr><td>

**👥 관원 총람 · Officials**
- 토큰 소비 랭킹
- 활동도 · 완료수 · 세션 통계

</td><td>

**📰 천하요문 · News**
- 매일 자동으로 IT/금융 뉴스 수집
- 카테고리 구독 관리 + Feishu 푸시

</td></tr>
<tr><td>

**⚙️ 모델 설정 · Models**
- 각 Agent 마다 LLM 독립 전환
- 적용 후 Gateway 자동 재시작 (~5초 적용)

</td><td>

**🛠️ 스킬 설정 · Skills**
- 각 부서에 설치된 Skills 일람
- 상세 보기 + 신규 스킬 추가

</td></tr>
<tr><td>

**💬 소작업 · Sessions**
- OC-* 세션 실시간 모니터링
- 출처 채널 · 하트비트 · 메시지 미리보기

</td><td>

**🎬 조회 의례 · Ceremony**
- 매일 첫 접속 시 오프닝 애니메이션 재생
- 오늘의 통계 · 3.5초 자동 사라짐

</td></tr>
<tr><td>

**🏛️ 조정 의정 · Court Discussion**
- 다수 관원이 의제를 두고 부서 시각으로 토론
- LLM 기반 다역할 토론 (각 부서가 직무에 따라 전문 의견 제시)
- 다중 라운드 진행 · 결론 요약 · 토론 기록 보존

</td><td>

</td></tr>
</table>

---

## 🖼️ 스크린샷

### 지시 칸반
![지시 칸반](docs/screenshots/01-kanban-main.png)

<details>
<summary>📸 더 많은 스크린샷 보기</summary>

### 부서 모니터
![부서 모니터](docs/screenshots/02-monitor.png)

### 작업 흐름 상세
![작업 흐름 상세](docs/screenshots/03-task-detail.png)

### 모델 설정
![모델 설정](docs/screenshots/04-model-config.png)

### 스킬 설정
![스킬 설정](docs/screenshots/05-skills-config.png)

### 관원 총람
![관원 총람](docs/screenshots/06-official-overview.png)

### 세션 기록
![세션 기록](docs/screenshots/07-sessions.png)

### 회보 보관
![회보 보관](docs/screenshots/08-memorials.png)

### 어명 템플릿
![어명 템플릿](docs/screenshots/09-templates.png)

### 천하요문
![천하요문](docs/screenshots/10-morning-briefing.png)

### 조회 의례
![조회 의례](docs/screenshots/11-ceremony.png)

</details>

---

## 🚀 30초 빠른 체험

### Docker 원클릭 시작

```bash
docker run -p 7891:7891 cft0808/sansheng-demo
```
http://localhost:7891 을 열면 군기처 칸반을 체험할 수 있습니다.

<details>
<summary><b>⚠️ <code>exec format error</code> 가 뜬다면? (펼치기)</b></summary>

**x86/amd64** 머신 (Ubuntu, WSL2 등) 에서 다음과 같이 보이는 경우:
```
exec /usr/local/bin/python3: exec format error
```

이는 이미지 아키텍처 불일치 때문입니다. `--platform` 매개변수를 사용하세요:
```bash
docker run --platform linux/amd64 -p 7891:7891 cft0808/sansheng-demo
```

또는 docker-compose 사용 (이미 `platform: linux/amd64` 내장):
```bash
docker compose up
```

</details>

### 완전 설치

#### 사전 조건
- [OpenClaw](https://openclaw.ai) 설치 완료
- Python 3.9+
- macOS / Linux

#### 설치

```bash
git clone https://github.com/cft0808/edict.git
cd edict
chmod +x install.sh && ./install.sh
```

설치 스크립트가 자동으로 수행:
- ✅ 전체 Agent Workspace 생성 (세자/이조/조보관 포함, 과거 main 호환)
- ✅ 각 부서 SOUL.md 작성 (역할 인격 + 워크플로우 규칙 + 데이터 정제 규범)
- ✅ Agent 및 권한 매트릭스를 `openclaw.json` 에 등록
- ✅ **데이터 통합 심볼릭 링크** (각 Workspace 의 data/scripts → 프로젝트 디렉터리, 데이터 일관성 확보)
- ✅ **Agent 간 통신 가시성 설정** (`sessions.visibility all`, 메시지 도달 불능 문제 해결)
- ✅ **API Key 모든 Agent 동기화** (구성된 Agent 에서 자동 복사)
- ✅ React 프론트엔드 빌드 (Node.js 18+ 필요, 미설치 시 건너뜀)
- ✅ 데이터 디렉터리 초기화 + 첫 데이터 동기화 (관원 통계 포함)
- ✅ Gateway 재시작으로 설정 적용

> ⚠️ **첫 설치**: 먼저 API Key 설정 필요: `openclaw agents add taizi`, 이후 `./install.sh` 재실행하여 모든 Agent 에 동기화.

#### 시작

```bash
# 방식 1: 원클릭 시작 (추천)
chmod +x start.sh && ./start.sh

# 방식 2: 분리 시작
bash scripts/run_loop.sh &      # 데이터 갱신 루프
python3 dashboard/server.py     # 칸반 서버

# 브라우저 열기
open http://127.0.0.1:7891
```

<details>
<summary><b>🖥️ 운영 환경 배포 (systemd)</b></summary>

```bash
# systemd 서비스 설치
sudo cp edict.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable edict
sudo systemctl start edict

# 또는 관리 스크립트 사용
bash edict.sh start    # 시작
bash edict.sh status   # 상태 보기
bash edict.sh restart  # 재시작
bash edict.sh stop     # 정지
```

</details>

> 💡 **칸반은 즉시 사용 가능**: `server.py` 가 `dashboard/dashboard.html` 을 내장. Docker 이미지에는 사전 빌드된 React 프론트엔드 포함

> 💡 자세한 튜토리얼은 [Getting Started 가이드](docs/getting-started.md) 참조

---

## 🏛️ 아키텍처

```
                           ┌───────────────────────────────────┐
                           │          👑 임금 (당신)              │
                           │     Feishu · Telegram · Signal     │
                           └─────────────────┬─────────────────┘
                                             │ 하지
                           ┌─────────────────▼─────────────────┐
                           │          👶 세자 (taizi)            │
                           │   분류: 잡담은 직접 회신 / 지시는 작업 생성 │
                           └─────────────────┬─────────────────┘
                                             │ 전지
                           ┌─────────────────▼─────────────────┐
                           │          📜 홍문관 (zhongshu)       │
                           │       지시 접수 → 기획 → 하위작업 분해      │
                           └─────────────────┬─────────────────┘
                                             │ 심의 제출
                           ┌─────────────────▼─────────────────┐
                           │          🔍 사간원 (menxia)         │
                           │       방안 심의 → 승인 / 반려 🚫       │
                           └─────────────────┬─────────────────┘
                                             │ 승인 ✅
                           ┌─────────────────▼─────────────────┐
                           │          📮 승정원 (shangshu)       │
                           │     작업 배분 → 6조 조율 → 회보 취합     │
                           └───┬──────┬──────┬──────┬──────┬───┘
                               │      │      │      │      │
                         ┌─────▼┐ ┌───▼───┐ ┌▼─────┐ ┌───▼─┐ ┌▼─────┐
                         │💰 호조│ │📝 예조│ │⚔️ 병조│ │⚖️ 형조│ │🔧 공조│
                         │ 데이터│ │ 문서  │ │ 엔지니어│ │ 컴플라이언스│ │ 인프라│
                         └──────┘ └──────┘ └──────┘ └─────┘ └──────┘
                                                               ┌──────┐
                                                               │📋 이조│
                                                               │ 인사  │
                                                               └──────┘
```

### 각 부서 직무

| 부서 | Agent ID | 직무 | 전문 영역 |
|------|----------|------|---------|
| 👶 **세자** | `taizi` | 메시지 분류, 요건 정리 | 잡담 식별, 지시 정제, 제목 요약 |
| 📜 **홍문관** | `zhongshu` | 지시 접수, 기획, 분해 | 요건 이해, 작업 분해, 방안 설계 |
| 🔍 **사간원** | `menxia` | 심의, 관문, 반려 | 품질 심사, 위험 식별, 표준 통제 |
| 📮 **승정원** | `shangshu` | 배분, 조율, 취합 | 작업 스케줄링, 진척 추적, 결과 통합 |
| 💰 **호조** | `hubu` | 데이터, 자원, 정산 | 데이터 처리, 보고서 생성, 비용 분석 |
| 📝 **예조** | `libu` | 문서, 규범, 보고 | 기술 문서, API 문서, 규범 제정 |
| ⚔️ **병조** | `bingbu` | 코드, 알고리즘, 점검 | 기능 개발, Bug 수정, 코드 리뷰 |
| ⚖️ **형조** | `xingbu` | 보안, 컴플라이언스, 감사 | 보안 스캔, 컴플라이언스 점검, 레드라인 통제 |
| 🔧 **공조** | `gongbu` | CI/CD, 배포, 도구 | Docker 설정, 파이프라인, 자동화 |
| 📋 **이조** | `libu_hr` | 인사, Agent 관리 | Agent 등록, 권한 유지, 교육 |
| 🌅 **조보관** | `zaochao` | 일일 조회, 뉴스 집계 | 정시 보도, 데이터 취합 |

### 권한 매트릭스

> 보내고 싶다고 보낼 수 없다 —— 진짜 분권 견제

| From ↓ \ To → | 세자 | 홍문관 | 사간원 | 승정원 | 호 | 예 | 병 | 형 | 공 | 이 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **세자** | — | ✅ | | | | | | | | |
| **홍문관** | ✅ | — | ✅ | ✅ | | | | | | |
| **사간원** | | ✅ | — | ✅ | | | | | | |
| **승정원** | | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **6조+이조** | | | | ✅ | | | | | | |

### 작업 상태 전이

```
임금 → 세자 분류 → 홍문관 기획 → 사간원 심의 → 배분 완료 → 집행 중 → 검토 대기 → ✅ 완료
                      ↑          │                              │
                      └──── 반려 ─┘                    중단 Blocked
```

> ⚡ **상태 전이 보호**: `kanban_update.py` 내장 `_VALID_TRANSITIONS` 상태 머신 검증,
> 비정상 점프 (예: Doing→Taizi) 는 거부되고 로그 기록되어 흐름 우회 불가능.
>
> 🔄 **비동기 이벤트 구동**: 서비스 간 Redis Streams EventBus 로 디커플링 통신, Outbox Relay 가 이벤트 신뢰 전달 보장.
> 모든 상태 변경은 감사 로그 (`audit.py`) 에 자동 기록되어 완전 추적 지원.

---

## 📁 프로젝트 구조

```
edict/
├── agents/                     # 12개 Agent 인격 템플릿
│   ├── taizi/SOUL.md           # 세자 · 메시지 분류 (지시 제목 규범 포함)
│   ├── zhongshu/SOUL.md        # 홍문관 · 기획 중추
│   ├── menxia/SOUL.md          # 사간원 · 심의 관문
│   ├── shangshu/SOUL.md        # 승정원 · 배분 두뇌
│   ├── hubu/SOUL.md            # 호조 · 데이터 자원
│   ├── libu/SOUL.md            # 예조 · 문서 규범
│   ├── bingbu/SOUL.md          # 병조 · 엔지니어 구현
│   ├── xingbu/SOUL.md          # 형조 · 컴플라이언스 감사
│   ├── gongbu/SOUL.md          # 공조 · 인프라
│   ├── libu_hr/                # 이조 · 인사 관리
│   └── zaochao/SOUL.md         # 조보관 · 정보 허브
├── dashboard/
│   ├── dashboard.html          # 군기처 칸반 (단일 파일 · 무의존성 · ~2500줄)
│   ├── dist/                   # React 프론트엔드 빌드 산출물 (Docker 이미지 포함, 로컬 선택)
│   ├── auth.py                 # Dashboard 로그인 인증
│   ├── court_discuss.py        # 조정 의정 (다관원 LLM 토론 엔진)
│   └── server.py               # API 서버 (Python 표준 라이브러리 · 무의존성 · ~2300줄)
├── edict/backend/              # 비동기 백엔드 서비스 (SQLAlchemy + Redis)
│   ├── app/models/
│   │   ├── task.py             # 작업 모델 + 상태 머신
│   │   ├── audit.py            # 감사 로그 모델
│   │   └── outbox.py           # Outbox 메시지 모델
│   ├── app/services/
│   │   ├── event_bus.py        # Redis Streams EventBus
│   │   └── task_service.py     # 작업 서비스 계층
│   └── app/workers/
│       ├── dispatch_worker.py  # 병렬 배분 + 재시도 + 자원 락
│       ├── orchestrator_worker.py  # DAG 오케스트레이터
│       └── outbox_relay.py     # 트랜잭션 Outbox Relay
├── agents/
│   ├── <agent_id>/SOUL.md      # 각 부서 Agent 인격 템플릿
│   ├── GLOBAL.md               # 전역 Agent 설정
│   └── groups/                 # Agent 그룹 (sansheng / liubu)
├── scripts/
│   ├── run_loop.sh             # 데이터 갱신 루프 (15초 주기)
│   ├── kanban_update.py        # 칸반 CLI (지시 데이터 정제 + 제목 검증 + 상태 머신)
│   ├── skill_manager.py        # Skill 관리 도구 (원격/로컬 Skills 추가, 갱신, 제거)
│   ├── agentrec_advisor.py     # Agent 모델 추천 (공과 장부 + 비용 최적화)
│   ├── linucb_router.py        # LinUCB 지능 라우팅
│   ├── refresh_watcher.py      # 데이터 변경 감시
│   ├── sync_from_openclaw_runtime.py
│   ├── sync_agent_config.py
│   ├── sync_officials_stats.py
│   ├── fetch_morning_news.py
│   ├── refresh_live_data.py
│   ├── apply_model_changes.py
│   └── file_lock.py            # 파일 락 (다중 Agent 동시 쓰기 방지)
├── tests/
│   ├── test_e2e_kanban.py      # 종단 간 테스트 (17개 단언)
│   └── test_state_machine_consistency.py  # 상태 머신 일관성 테스트
├── data/                       # 런타임 데이터 (gitignored)
├── docs/
│   ├── task-dispatch-architecture.md  # 📚 상세 아키텍처 문서: 작업 배분, 흐름, 스케줄링의 완전 설계 (비즈니스+기술)
│   ├── getting-started.md             # 빠른 시작 가이드
│   ├── joseon-localization-plan.md    # 한글화 / 조선식 개편 계획
│   └── screenshots/                   # 기능 스크린샷 (11장)
├── install.sh                  # 원클릭 설치 스크립트
├── start.sh                    # 원클릭 시작 (Dashboard + 데이터 갱신)
├── edict.service               # systemd 서비스 설정 (운영 배포)
├── edict.sh                    # 서비스 관리 스크립트 (start/stop/restart/status)
└── LICENSE                     # MIT License
```

---

## 🎯 사용 방법

### AI 에 하지

Feishu / Telegram / Signal 로 홍문관에 메시지 발송:

```
사용자 등록 시스템을 설계해 줘. 요구사항:
1. RESTful API (FastAPI)
2. PostgreSQL 데이터베이스
3. JWT 인증
4. 완전한 테스트 케이스
5. 배포 문서
```

**그리고 자리 잡고 앉아 구경하세요:**

1. 📜 홍문관 지시 접수, 하위 작업 배분 방안 기획
2. 🔍 사간원 심의, 통과 / 반려하여 다시 기획
3. 📮 승정원 승인, 병조 + 공조 + 예조 에 배분
4. ⚔️ 각 부서 병렬 집행, 진척 실시간 가시화
5. 📮 승정원 결과 취합, 당신에게 회보

전 과정을 **군기처 칸반** 에서 실시간 모니터링하며, 언제든 **중지·취소·재개** 가능.

### 어명 템플릿 사용

> 칸반 → 📜 어명 라이브러리 → 템플릿 선택 → 매개변수 입력 → 하지

9개 사전 설정 템플릿: 주간 보고서 · 코드 리뷰 · API 설계 · 경쟁사 분석 · 데이터 보고서 · 블로그 글 · 배포 방안 · 이메일 카피 · 스탠드업 요약

### Agent 커스터마이징

`agents/<id>/SOUL.md` 를 편집하여 Agent 의 인격, 직무, 출력 규범 수정.

### Skills 추가 (인터넷에서 연결)

**Skills 추가 3가지 방법:**

#### 1️⃣ 칸반 UI (가장 간단)

```
칸반 → 🔧 스킬 설정 → ➕ 원격 Skill 추가
→ Agent + Skill 이름 + GitHub URL 입력
→ 확인 → ✅ 완료
```

#### 2️⃣ CLI 명령 (가장 유연)

```bash
# GitHub 에서 code_review skill 을 홍문관에 추가
python3 scripts/skill_manager.py add-remote \
  --agent zhongshu \
  --name code_review \
  --source https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md \
  --description "코드 리뷰 스킬"

# 공식 skills 라이브러리를 지정 agents 에 일괄 임포트
python3 scripts/skill_manager.py import-official-hub \
  --agents zhongshu,menxia,shangshu,bingbu,xingbu

# 추가된 모든 원격 skills 나열
python3 scripts/skill_manager.py list-remote

# 특정 skill 을 최신 버전으로 갱신
python3 scripts/skill_manager.py update-remote \
  --agent zhongshu \
  --name code_review
```

#### 3️⃣ API 요청 (자동화 통합)

```bash
# 원격 skill 추가
curl -X POST http://localhost:7891/api/add-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "zhongshu",
    "skillName": "code_review",
    "sourceUrl": "https://raw.githubusercontent.com/...",
    "description": "코드 리뷰"
  }'

# 모든 원격 skills 보기
curl http://localhost:7891/api/remote-skills-list
```

**공식 Skills Hub:** https://github.com/openclaw-ai/skills-hub

지원 Skills:
- `code_review` — 코드 리뷰 (Python/JS/Go)
- `api_design` — API 설계 리뷰
- `security_audit` — 보안 감사
- `data_analysis` — 데이터 분석
- `doc_generation` — 문서 생성
- `test_framework` — 테스트 프레임워크 설계

자세한 내용은 [🎓 원격 Skills 자원 관리 가이드](docs/remote-skills-guide.md) 참조

---

## 🔧 기술 하이라이트

| 특징 | 설명 |
|------|------|
| **React 18 프론트엔드** | TypeScript + Vite + Zustand 상태 관리, 13개 기능 컴포넌트 |
| **순수 stdlib 백엔드** | `server.py` 는 `http.server` 기반, 무의존성, API + 정적 파일 서비스 동시 제공 |
| **EventBus 이벤트 버스** | Redis Streams 발행/구독, 서비스 간 디커플링 통신 |
| **Outbox Relay** | 트랜잭션 Outbox 패턴, 이벤트 신뢰 전달 보장 (at-least-once 의미) |
| **상태 머신 감사** | 엄격한 라이프사이클 상태 전환 + 완전 감사 로그 (`audit.py`) |
| **병렬 배분 엔진** | Dispatch Worker 가 병렬 실행, 지수 백오프 재시도, 자원 락 지원 |
| **DAG 오케스트레이터** | DAG 기반 작업 분해 및 의존 해석 |
| **Agent 사고 가시화** | Agent 의 thinking 과정, 도구 호출, 반환 결과 실시간 표시 |
| **원클릭 설치 / 시작** | `install.sh` 자동 설정, `start.sh` 한 줄로 모든 서비스 시작 |
| **systemd 운영 배포** | `edict.service` 가 systemd 데몬 지원, 부팅 자동 시작 |
| **15초 동기화** | 데이터 자동 갱신, 칸반에 카운트다운 표시 |
| **Dashboard 인증** | `auth.py` 가 칸반 로그인 인증 제공 |
| **일일 의례** | 첫 접속 시 조회 오프닝 애니메이션 재생 |
| **원격 Skills 생태** | GitHub/URL 에서 능력 원클릭 임포트, 버전 관리 + CLI + API + UI 지원 |

---

## 📚 더 알아보기

### 핵심 문서

- **[📖 작업 배분 흐름 완전 아키텍처](docs/task-dispatch-architecture.md)** — **필독 문서**
  - 3사6조가 복잡한 작업을 어떻게 처리하는지 비즈니스 설계와 기술 구현을 상세 설명
  - 다루는 내용: 9개 작업 상태 머신 / 권한 매트릭스 / 4단계 스케줄링 (재시도→에스컬레이션→롤백) / Session JSONL 데이터 통합
  - 완전한 사용 사례, API 엔드포인트 설명, CLI 도구 문서 포함
  - CrewAI/AutoGen 과의 비교: 왜 제도화 > 자유 협업인가
  - 장애 시나리오와 복구 메커니즘
  - **이 문서를 읽으면 3사6조가 왜 이렇게 강력한지 이해할 수 있습니다** (9500+ 자, 30분 완전 이해)

- **[🎓 원격 Skills 자원 관리 가이드](docs/remote-skills-guide.md)** — Skills 생태
  - 인터넷에서 skills 연결 및 추가, GitHub/Gitee/임의 HTTPS URL 지원
  - 공식 Skills Hub 사전 설정 능력 라이브러리
  - CLI 도구 + 칸반 UI + Restful API
  - Skills 파일 규범 및 보안 보호
  - 버전 관리 및 원클릭 갱신 지원

- **[⚡ Remote Skills 빠른 입문](docs/remote-skills-quickstart.md)** — 5분 시작
  - 빠른 체험, CLI 명령, 칸반 조작 예시
  - 자체 Skills 라이브러리 만들기
  - API 완전 참조 + FAQ

- **[🚀 빠른 시작 가이드](docs/getting-started.md)** — 초보자 입문
- **[📜 한글화 / 조선식 개편 계획](docs/joseon-localization-plan.md)** — 본 fork 의 한글화 기준 문서

---
## 🔧 자주 묻는 문제 해결

<details>
<summary><b>❌ 작업이 항상 타임아웃 / 부하는 완료했지만 세자에게 회신 안 됨</b></summary>

**증상**: 6조 또는 승정원이 작업을 완료했지만 세자가 회보를 받지 못해 결국 타임아웃.

**진단 절차**:

1. **Agent 등록 상태 확인**:
```bash
curl -s http://127.0.0.1:7891/api/agents-status | python3 -m json.tool
```
`taizi` agent 의 `statusLabel` 이 `alive` 인지 확인.

2. **Gateway 로그 확인**:
```bash
ls /tmp/openclaw/ | tail -5          # 최신 로그 찾기
grep -i "error\|fail\|unknown" /tmp/openclaw/openclaw-*.log | tail -20
```

3. **흔한 원인**:
   - Agent ID 불일치 (v1.2 에서 수정됨: `main` → `taizi`)
   - LLM provider 타임아웃 (자동 재시도 추가됨)
   - 좀비 Agent 프로세스 (`ps aux | grep openclaw` 로 확인)

4. **강제 재시도**:
```bash
# 점검 스캔 수동 트리거 (멈춘 작업 자동 재시도)
curl -X POST http://127.0.0.1:7891/api/scheduler-scan \
  -H 'Content-Type: application/json' -d '{"thresholdSec":60}'
```

</details>

<details>
<summary><b>❌ Docker: exec format error</b></summary>

**증상**: `exec /usr/local/bin/python3: exec format error`

**원인**: 이미지 아키텍처 (arm64) 와 호스트 아키텍처 (amd64) 불일치.

**해결**:
```bash
# 방법 1: 플랫폼 명시
docker run --platform linux/amd64 -p 7891:7891 cft0808/sansheng-demo

# 방법 2: docker-compose 사용 (platform 내장)
docker compose up
```

</details>

<details>
<summary><b>❌ Skill 다운로드 실패</b></summary>

**증상**: `python3 scripts/skill_manager.py import-official-hub` 오류.

**진단**:
```bash
# 네트워크 연결성 테스트
curl -I https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md

# 타임아웃 시 프록시 사용
export https_proxy=http://your-proxy:port
python3 scripts/skill_manager.py import-official-hub --agents zhongshu
```

**흔한 원인**:
- 일부 지역에서 GitHub raw 자원 접근 시 프록시 필요
- 네트워크 타임아웃 (30초로 증가 + 자동 재시도 3회)
- 공식 Skills Hub 저장소 점검 중

</details>

---
## 🗺️ Roadmap

### Phase 1 — 핵심 아키텍처 ✅
- [x] 12부제 Agent 아키텍처 (세자 + 3사 + 7조 + 조보관) + 권한 매트릭스
- [x] 군기처 실시간 칸반 (10개 기능 패널 + 실시간 활동 패널)
- [x] 작업 중지 / 취소 / 재개
- [x] 회보 시스템 (자동 보관 + 5단계 타임라인)
- [x] 어명 템플릿 라이브러리 (9개 사전 설정 + 매개변수 폼)
- [x] 조회 의례 애니메이션
- [x] 천하요문 + Feishu 푸시 + 구독 관리
- [x] 모델 핫스왑 + 스킬 관리 + 스킬 추가
- [x] 관원 총람 + 토큰 소비 통계
- [x] 소작업 / 세션 모니터링
- [x] 세자 메시지 분류 (잡담 자동 회신 / 지시 작업 생성)
- [x] 지시 데이터 정제 (경로/메타데이터/접두어 자동 제거)
- [x] 중복 작업 보호 + 완료 작업 보호
- [x] 종단 간 테스트 커버리지 (17개 단언)
- [x] React 18 프론트엔드 리팩터링 (TypeScript + Vite + Zustand · 13 컴포넌트)
- [x] Agent 사고 과정 시각화 (실시간 thinking / 도구 호출 / 반환 결과)
- [x] 프론트백 일체 배포 (server.py 가 API + 정적 파일 서비스 동시 제공)

### Phase 2 — 제도 심화 🚧
- [ ] 어비 모드 (수동 결재 + 원클릭 승인/반려)
- [x] 공과 장부 (Agent 성과 점수 + 모델 추천 + 비용 최적화)
- [x] EventBus 이벤트 버스 (Redis Streams 디커플링 통신)
- [x] Outbox Relay (트랜잭션 이벤트 전달)
- [x] 상태 머신 감사 (엄격한 라이프사이클 + 감사 로그)
- [x] 병렬 배분 엔진 (지수 백오프 재시도 + 자원 락)
- [x] DAG 오케스트레이터 (작업 분해 + 의존 해석)
- [x] Dashboard 인증 (로그인 인증)
- [x] 원클릭 시작 / systemd 운영 배포
- [ ] 급체국 (Agent 간 실시간 메시지 흐름 시각화)
- [ ] 국사관 (지식 베이스 검색 + 인용 추적)

### Phase 3 — 생태 확장
- [ ] Docker Compose + Demo 이미지
- [ ] Notion / Linear 어댑터
- [ ] 연도 대고 (Agent 연도 성과 보고서)
- [ ] 모바일 적응 + PWA
- [ ] ClawHub 등록

---

## 📂 사례

`examples/` 디렉터리에 실제 종단 간 사용 사례 수록:

| 사례 | 지시 | 관여 부서 |
|------|------|----------|
| [경쟁사 분석](examples/competitive-analysis.md) | "CrewAI vs AutoGen vs LangGraph 분석" | 홍문관→사간원→호조+병조+예조 |
| [코드 리뷰](examples/code-review.md) | "이 FastAPI 코드의 보안성 검토" | 홍문관→사간원→병조+형조 |
| [주간 보고서 생성](examples/weekly-report.md) | "이번 주 엔지니어링 팀 주간 보고서 생성" | 홍문관→사간원→호조+예조 |

각 사례 포함: 완전한 지시 → 홍문관 기획 → 사간원 심의 의견 → 각 부서 집행 결과 → 최종 회보.

---

## 📄 License

[MIT](LICENSE) · [OpenClaw](https://openclaw.ai) 커뮤니티가 구축

이 저장소는 [원본 프로젝트](https://github.com/cft0808/edict) 를 fork 하여 한국어 / 조선식 운영 체계로 재해석한 버전입니다. 한글화 기준은 [docs/joseon-localization-plan.md](docs/joseon-localization-plan.md) 참조.

---

<p align="center">
  <strong>⚔️ 옛 제도로 새 기술을 다스리고, 지혜로 AI 를 부린다</strong><br>
  <sub>Governing AI with the wisdom of ancient empires</sub>
</p>
