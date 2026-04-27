# 원격 스킬 자원 관리 가이드

## 개요

3사6조는 이제 네트워크에서 스킬 자원을 연결하고 보강할 수 있도록 지원하며, 파일을 수동으로 복사할 필요가 없습니다. 다음 출처에서 가져올 수 있습니다.

- **GitHub 저장소** (raw.githubusercontent.com)
- **모든 HTTPS URL** (유효한 스킬 파일을 반환해야 함)
- **로컬 파일 경로**
- **내장 저장소** (공식 스킬 라이브러리)

---

## 기능 아키텍처

### 1. API 엔드포인트

#### `POST /api/add-remote-skill`

원격 URL 또는 로컬 경로에서 지정된 Agent 에 스킬을 추가합니다.

**요청 본문:**
```json
{
  "agentId": "zhongshu",
  "skillName": "code_review",
  "sourceUrl": "https://raw.githubusercontent.com/org/skills-repo/main/code_review/SKILL.md",
  "description": "코드 리뷰 전문 스킬"
}
```

**매개변수 설명:**
- `agentId` (string, 필수): 대상 Agent ID (유효성 검증)
- `skillName` (string, 필수): 스킬의 내부 이름 (영문/숫자/밑줄/한글만 허용)
- `sourceUrl` (string, 필수): 원격 URL 또는 로컬 파일 경로
  - GitHub: `https://raw.githubusercontent.com/user/repo/branch/path/SKILL.md`
  - 임의 HTTPS: `https://example.com/skills/my_skill.md`
  - 로컬: `file:///Users/bingsen/skills/code_review.md` 또는 `/Users/bingsen/skills/code_review.md`
- `description` (string, 선택): 스킬에 대한 한국어 설명

**성공 응답 (200):**
```json
{
  "ok": true,
  "message": "스킬 code_review 가 zhongshu 에 추가되었습니다",
  "skillName": "code_review",
  "agentId": "zhongshu",
  "source": "https://raw.githubusercontent.com/...",
  "localPath": "/Users/bingsen/.openclaw/workspace-zhongshu/skills/code_review/SKILL.md",
  "size": 2048,
  "addedAt": "2026-03-02T14:30:00Z"
}
```

**실패 응답 (400):**
```json
{
  "ok": false,
  "error": "URL 이 유효하지 않거나 접근할 수 없습니다",
  "details": "Connection timeout after 10s"
}
```

#### `GET /api/remote-skills-list`

추가된 모든 원격 스킬과 출처 정보를 나열합니다.

**응답:**
```json
{
  "ok": true,
  "remoteSkills": [
    {
      "skillName": "code_review",
      "agentId": "zhongshu",
      "sourceUrl": "https://raw.githubusercontent.com/org/skills-repo/main/code_review/SKILL.md",
      "description": "코드 리뷰 전문 스킬",
      "localPath": "/Users/bingsen/.openclaw/workspace-zhongshu/skills/code_review/SKILL.md",
      "lastUpdated": "2026-03-02T14:30:00Z",
      "status": "valid"  // valid | invalid | not-found
    }
  ],
  "count": 5
}
```

#### `POST /api/update-remote-skill`

추가된 원격 스킬을 최신 버전으로 갱신합니다.

**요청 본문:**
```json
{
  "agentId": "zhongshu",
  "skillName": "code_review"
}
```

**응답:**
```json
{
  "ok": true,
  "message": "스킬이 갱신되었습니다",
  "skillName": "code_review",
  "newVersion": "2.1.0",
  "updatedAt": "2026-03-02T15:00:00Z"
}
```

#### `DELETE /api/remove-remote-skill`

추가된 원격 스킬을 제거합니다.

**요청 본문:**
```json
{
  "agentId": "zhongshu",
  "skillName": "code_review"
}
```

---

## CLI 명령

### 원격 스킬 추가

```bash
python3 scripts/skill_manager.py add-remote \
  --agent zhongshu \
  --name code_review \
  --source https://raw.githubusercontent.com/org/skills-repo/main/code_review/SKILL.md \
  --description "코드 리뷰 전문 스킬"
```

### 원격 스킬 나열

```bash
python3 scripts/skill_manager.py list-remote
```

### 원격 스킬 갱신

```bash
python3 scripts/skill_manager.py update-remote \
  --agent zhongshu \
  --name code_review
```

### 원격 스킬 제거

```bash
python3 scripts/skill_manager.py remove-remote \
  --agent zhongshu \
  --name code_review
```

---

## 공식 스킬 저장소

### OpenClaw Skills Hub

> **공식 스킬 저장소 주소**: https://github.com/openclaw-ai/skills-hub

사용 가능한 스킬 목록:

| 스킬 이름 | 설명 | 적용 Agent | 출처 URL |
|-----------|------|----------|--------|
| `code_review` | 코드 리뷰 (Python/JS/Go 지원) | 병조/형조 | https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md |
| `api_design` | API 설계 리뷰 | 병조/공조 | https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/api_design/SKILL.md |
| `security_audit` | 보안 감사 | 형조 | https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/security_audit/SKILL.md |
| `data_analysis` | 데이터 분석 | 호조 | https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/data_analysis/SKILL.md |
| `doc_generation` | 문서 생성 | 예조 | https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/doc_generation/SKILL.md |
| `test_framework` | 테스트 프레임워크 설계 | 공조/형조 | https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/test_framework/SKILL.md |

**공식 스킬 일괄 가져오기**

```bash
python3 scripts/skill_manager.py import-official-hub \
  --agents zhongshu,menxia,shangshu,bingbu,xingbu,libu
```

---

## 칸반 UI 조작

### 빠르게 스킬 추가하기

1. 칸반 열기 → 🔧 **스킬 설정** 패널
2. **➕ 원격 스킬 추가** 버튼 클릭
3. 양식 작성:
   - **Agent**: 대상 Agent 선택
   - **스킬 이름**: 스킬 내부 ID 입력
   - **원격 URL**: GitHub/HTTPS URL 붙여넣기
   - **한국어 설명**: 선택, 스킬 기능을 간단히 기술
4. **확인** 버튼 클릭

### 추가된 스킬 관리

1. 칸반 → 🔧 **스킬 설정** → **원격 스킬** 탭
2. 추가된 모든 스킬과 출처 주소 조회
3. 작업:
   - **조회**: SKILL.md 내용 표시
   - **갱신**: 출처 URL 에서 최신 버전을 다시 다운로드
   - **삭제**: 로컬 사본 제거 (출처에는 영향 없음)
   - **출처 URL 복사**: 다른 사람과 빠르게 공유

---

## 스킬 파일 규격

원격 스킬은 표준 Markdown 형식을 반드시 따라야 합니다.

### 최소 필수 구조

```markdown
---
name: skill_internal_name
description: Short description
version: 1.0.0
tags: [tag1, tag2]
---

# 스킬 이름

상세 설명...

## 입력

어떤 매개변수를 받는지 설명

## 처리 흐름

구체적인 단계...

## 출력 규격

출력 형식 설명
```

### 완전한 예시

```markdown
---
name: code_review
description: Python/JavaScript 코드에 대한 구조 리뷰와 최적화 제안
version: 2.1.0
author: openclaw-ai
tags: [code-quality, security, performance]
compatibleAgents: [bingbu, xingbu, menxia]
---

# 코드 리뷰 스킬

본 스킬은 운영 코드에 대한 다차원 리뷰 전용입니다...

## 입력

- `code`: 리뷰할 소스 코드
- `language`: 프로그래밍 언어 (python, javascript, go, rust)
- `focusAreas`: 리뷰 중점 (security, performance, style, structure)

## 처리 흐름

1. 언어 식별 및 문법 검증
2. 보안 취약점 스캔
3. 성능 병목 식별
4. 코드 스타일 검사
5. 모범 사례 제안

## 출력 규격

```json
{
  "issues": [
    {
      "type": "security|performance|style|structure",
      "severity": "critical|high|medium|low",
      "location": "line:column",
      "message": "문제 설명",
      "suggestion": "수정 제안"
    }
  ],
  "summary": {
    "totalIssues": 3,
    "criticalCount": 1,
    "highCount": 2
  }
}
```

## 적용 시나리오

- 병조(코드 구현)의 코드 산출물 리뷰
- 형조(규정 감사)의 보안 점검
- 사간원(심의 검토)의 품질 평가

## 의존성과 제한

- Python 3.9+ 필요
- 지원 파일 크기: 최대 50KB
- 실행 시간 제한: 30초
```

---

## 데이터 저장

### 로컬 저장 구조

```
~/.openclaw/
├── workspace-zhongshu/
│   └── skills/
│       ├── code_review/
│       │   ├── SKILL.md
│       │   └── .source.json    # 출처 URL 과 메타데이터 저장
│       └── api_design/
│           ├── SKILL.md
│           └── .source.json
├── ...
```

### .source.json 형식

```json
{
  "skillName": "code_review",
  "sourceUrl": "https://raw.githubusercontent.com/...",
  "description": "코드 리뷰 전문 스킬",
  "version": "2.1.0",
  "addedAt": "2026-03-02T14:30:00Z",
  "lastUpdated": "2026-03-02T14:30:00Z",
  "lastUpdateCheck": "2026-03-02T15:00:00Z",
  "checksum": "sha256:abc123...",
  "status": "valid"
}
```

---

## 보안 고려사항

### URL 검증

✅ **허용되는 URL 유형:**
- HTTPS URL: `https://`
- 로컬 파일: `file://` 또는 절대 경로
- 상대 경로: `./skills/`

❌ **금지된 URL 유형:**
- HTTP (HTTPS 가 아님): `http://` 는 거부됨
- 로컬 모드 HTTP: `http://localhost/` (루프백 공격 회피)
- FTP/SSH: `ftp://`, `ssh://`

### 내용 검증

1. **형식 검증**: 유효한 Markdown YAML frontmatter 인지 확인
2. **크기 제한**: 최대 10 MB
3. **타임아웃 보호**: 다운로드가 30초를 초과하면 자동 중단
4. **경로 탐색 방어**: 파싱된 스킬 이름 검사, `../` 패턴 금지
5. **checksum 검증**: 선택적 GPG 서명 검증 (공식 저장소만 해당)

### 격리 실행

- 원격 스킬은 샌드박스에서 실행됩니다 (OpenClaw runtime 이 제공)
- `~/.openclaw/config.json` 등 민감한 파일에는 접근 불가
- 할당된 workspace 디렉터리에만 접근 가능

---

## 문제 해결

### 자주 묻는 질문

**Q: 다운로드 실패, "Connection timeout" 표시**

A: 네트워크 연결과 URL 유효성을 확인:
```bash
curl -I https://raw.githubusercontent.com/...
```

**Q: 스킬이 "invalid" 상태로 표시됨**

A: 파일 형식을 확인:
```bash
python3 -m json.tool ~/.openclaw/workspace-zhongshu/skills/xxx/SKILL.md
```

**Q: 비공개 GitHub 저장소에서 가져올 수 있나요?**

A: 지원하지 않습니다 (보안상). 다음 방법을 사용할 수 있습니다:
1. 저장소를 공개로 전환
2. 로컬에 다운로드 후 직접 추가
3. GitHub Gist 의 공개 링크 사용

**Q: 자체 스킬 저장소를 만들려면?**

A: [OpenClaw Skills Hub](https://github.com/openclaw-ai/skills-hub) 의 구조를 참고하여 자체 저장소를 만든 다음:

```bash
git clone https://github.com/yourname/my-skills-hub.git
cd my-skills-hub
# 스킬 파일 구조 생성
# 커밋 & GitHub 에 푸시
```

이후 URL 또는 공식 저장소 가져오기 기능으로 추가하면 됩니다.

---

## 모범 사례

### 1. 버전 관리

SKILL.md 의 frontmatter 에 항상 버전 번호를 명시하세요:
```yaml
---
version: 2.1.0
---
```

### 2. 하위 호환

스킬을 갱신할 때 입력/출력 형식을 호환되도록 유지하여 기존 흐름이 깨지지 않게 합니다.

### 3. 문서 완비

다음을 포함하세요:
- 기능 설명
- 적용 시나리오
- 의존성 설명
- 출력 예시

### 4. 정기 갱신

정기적인 갱신 점검을 설정합니다 (주기는 칸반에서 설정 가능):
```bash
python3 scripts/skill_manager.py check-updates --interval weekly
```

### 5. 커뮤니티 기여

성숙한 스킬은 [OpenClaw Skills Hub](https://github.com/openclaw-ai/skills-hub) 에 기여할 수 있습니다.

---

## API 전체 참조

자세한 내용은 [작업 분배 흐름 아키텍처 문서](task-dispatch-architecture.md) 의 제3부 (API 와 도구) 참조.

---

<p align="center">
  <sub><strong>개방형</strong> 생태계로 <strong>제도화된</strong> AI 협업을 지원합니다</sub>
</p>
