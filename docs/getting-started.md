# 🚀 빠른 시작 가이드

> 처음부터 5분 만에 구축하는 3사6조 AI 협업 시스템

---

## 1단계: OpenClaw 설치

3사6조는 [OpenClaw](https://openclaw.ai) 위에서 동작합니다. 먼저 설치하세요.

```bash
# macOS
brew install openclaw

# 또는 설치 패키지 다운로드
# https://openclaw.ai/download
```

설치가 끝나면 초기화합니다.

```bash
openclaw init
```

## 2단계: 3사6조 클론 및 설치

```bash
git clone https://github.com/cft0808/edict.git
cd edict
chmod +x install.sh && ./install.sh
```

설치 스크립트가 다음을 자동으로 수행합니다.
- ✅ 12개의 Agent Workspace 생성 (`~/.openclaw/workspace-*`)
- ✅ 각 사·조의 SOUL.md 인격 파일 기록
- ✅ Agent 및 권한 매트릭스를 `openclaw.json` 에 등록
- ✅ 지시 데이터 정제 규칙 구성
- ✅ React 프런트엔드를 `dashboard/dist/` 로 빌드 (Node.js 18+ 필요)
- ✅ 데이터 디렉터리 초기화
- ✅ 최초 데이터 동기화 수행
- ✅ Gateway 재시작으로 설정 적용

## 3단계: 메시지 채널 구성

OpenClaw 에서 메시지 채널 (Feishu(飞书) / Telegram / Signal) 을 구성하고, `taizi`(세자) Agent 를 지시 입구로 지정합니다. 세자는 잡담과 지시를 자동으로 분류하여, 지시성 메시지의 제목을 추출한 뒤 홍문관으로 전달합니다.

```bash
# 현재 채널 조회
openclaw channels list

# Feishu 채널 추가 (입구를 세자로 지정)
openclaw channels add --type feishu --agent taizi
```

OpenClaw 공식 문서 참고: https://docs.openclaw.ai/channels

## 4단계: 서비스 기동

```bash
# 터미널 1: 데이터 갱신 루프 (15초마다 동기화)
bash scripts/run_loop.sh

# 터미널 2: 칸반 서버
python3 dashboard/server.py

# 브라우저 열기
open http://127.0.0.1:7891
```

> 💡 **팁**: `run_loop.sh` 는 15초마다 자동으로 데이터를 동기화합니다. `&` 로 백그라운드 실행이 가능합니다.

> 💡 **칸반은 즉시 사용 가능**: `server.py` 는 `dashboard/dashboard.html` 을 내장하고 있어 별도 빌드가 필요 없습니다. Docker 이미지에는 사전 빌드된 React 프런트엔드가 포함됩니다.

## 5단계: 첫 번째 지시 보내기

메시지 채널을 통해 작업을 전달합니다 (세자가 자동으로 식별하여 홍문관으로 전달합니다).

```
Python 으로 텍스트 분류기를 만들어 주세요:
1. scikit-learn 사용
2. 다중 분류 지원
3. 혼동 행렬 출력
4. 문서 완비
```

## 6단계: 실행 과정 관찰

칸반을 엽니다. http://127.0.0.1:7891

1. **📋 지시 칸반** — 작업이 각 상태 사이를 흘러가는 모습을 관찰
2. **🔭 사·조 디스패치** — 각 부서별 작업 분포 확인
3. **📜 회보각** — 작업이 끝나면 회보로 자동 보관

작업 흐름 경로:
```
수신 → 세자 분류 → 홍문관 기획 → 사간원 심의 → 배정 완료 → 실행 중 → 완료
```

---

## 🎯 심화 활용

### 어명 템플릿 사용

> 칸반 → 📜 어명 라이브러리 → 템플릿 선택 → 파라미터 입력 → 하지

9가지 사전 정의 템플릿: 주간 보고서 · 코드 리뷰 · API 설계 · 경쟁사 분석 · 데이터 리포트 · 블로그 글 · 배포 방안 · 이메일 문안 · 스탠드업 요약

### Agent 모델 전환

> 칸반 → ⚙️ 모델 설정 → 새 모델 선택 → 변경 적용

약 5초 후 Gateway 가 자동으로 재시작되어 적용됩니다.

### 스킬 관리

> 칸반 → 🛠️ 스킬 설정 → 설치된 스킬 확인 → 새 스킬 추가 클릭

### 작업 중지 / 취소

> 지시 칸반 또는 작업 상세 화면에서 **⏸ 중지** 또는 **🚫 취소** 버튼을 클릭

### 천하요문(天下要闻) 구독

> 칸반 → 📰 천하요문 → ⚙️ 구독 관리 → 카테고리 선택 / 출처 추가 / Feishu 푸시 설정

---

## ❓ 문제 해결

### 칸반에 「서버가 실행 중이지 않습니다」가 표시됨
```bash
# 서버가 동작 중인지 확인
python3 dashboard/server.py
```

### Agent 가 "No API key found for provider" 오류를 출력함

가장 흔한 문제입니다. 3사6조에는 11개의 Agent 가 있으며 각 Agent 마다 API Key 가 필요합니다.

```bash
# 방법 1: 임의의 Agent 에 설정한 뒤 install.sh 를 다시 실행 (권장)
openclaw agents add taizi          # 안내에 따라 Anthropic API Key 입력
cd edict && ./install.sh            # 모든 Agent 로 자동 동기화

# 방법 2: auth 파일 수동 복사
MAIN_AUTH=$(find ~/.openclaw/agents -name auth-profiles.json | head -1)
for agent in taizi zhongshu menxia shangshu hubu libu bingbu xingbu gongbu; do
  mkdir -p ~/.openclaw/agents/$agent/agent
  cp "$MAIN_AUTH" ~/.openclaw/agents/$agent/agent/auth-profiles.json
done

# 방법 3: 하나씩 직접 설정
openclaw agents add taizi
openclaw agents add zhongshu
# ... 그 외 Agent
```

### Agent 가 응답하지 않음
```bash
# Gateway 상태 확인
openclaw gateway status

# 필요 시 재시작
openclaw gateway restart
```

### 데이터가 갱신되지 않음
```bash
# 갱신 루프가 동작 중인지 확인
ps aux | grep run_loop

# 동기화를 한 번 수동 실행
python3 scripts/refresh_live_data.py
```

### 하트비트가 빨간색 / 경보가 발생
```bash
# 해당 Agent 프로세스 점검
openclaw agent status <agent-id>

# 지정한 Agent 재시작
openclaw agent restart <agent-id>
```

### 모델 전환이 적용되지 않음
약 5초간 Gateway 재시작이 끝나기를 기다립니다. 그래도 적용되지 않으면 다음을 실행하세요.
```bash
python3 scripts/apply_model_changes.py
openclaw gateway restart
```

---

## 📚 더 많은 자료

- [🏠 프로젝트 홈페이지](https://github.com/cft0808/edict)
- [📖 README](../README.md)
- [🤝 기여 가이드](../CONTRIBUTING.md)
- [💬 OpenClaw 공식 문서](https://docs.openclaw.ai)
