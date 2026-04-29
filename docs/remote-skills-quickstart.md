# 원격 스킬 빠른 시작

## 5분 체험

### 1. 서버 시작

```bash
# 프로젝트 루트 디렉터리에 있는지 확인
python3 dashboard/server.py
# 출력: 3사6조 칸반 시작 → http://127.0.0.1:7891
```

### 2. 공식 스킬 추가 (CLI)

```bash
# 홍문관에 코드 리뷰 스킬 추가
python3 scripts/skill_manager.py add-remote \
  --agent hongmungwan \
  --name code_review \
  --source https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md \
  --description "코드 리뷰 능력"

# 출력:
# ⏳ https://raw.githubusercontent.com/... 에서 다운로드 중...
# ✅ 스킬 code_review 가 hongmungwan 에 추가되었습니다
#    경로: /Users/xxx/.openclaw/workspace-hongmungwan/skills/code_review/SKILL.md
#    크기: 2048 바이트
```

### 3. 모든 원격 스킬 나열

```bash
python3 scripts/skill_manager.py list-remote

# 출력:
# 📋 총 1개의 원격 스킬:
# 
# Agent       | 스킬 이름            | 설명                           | 추가 시각
# ------------|----------------------|--------------------------------|----------
# hongmungwan    | code_review          | 코드 리뷰 능력                 | 2026-03-02
```

### 4. API 응답 조회

```bash
curl http://localhost:7891/api/remote-skills-list | jq .

# 출력:
# {
#   "ok": true,
#   "remoteSkills": [
#     {
#       "skillName": "code_review",
#       "agentId": "hongmungwan",
#       "sourceUrl": "https://raw.githubusercontent.com/...",
#       "description": "코드 리뷰 능력",
#       "localPath": "/Users/xxx/.openclaw/workspace-hongmungwan/skills/code_review/SKILL.md",
#       "addedAt": "2026-03-02T14:30:00Z",
#       "lastUpdated": "2026-03-02T14:30:00Z",
#       "status": "valid"
#     }
#   ],
#   "count": 1,
#   "listedAt": "2026-03-02T14:35:00Z"
# }
```

---

## 자주 쓰는 작업

### 공식 저장소의 모든 스킬을 일괄 가져오기

```bash
python3 scripts/skill_manager.py import-official-hub \
  --agents hongmungwan,saganwon,seungjeongwon,byeongjo,hyeongjo
```

이렇게 하면 각 agent 에 다음이 자동 추가됩니다:
- **hongmungwan**: code_review, api_design, doc_generation
- **saganwon**: code_review, api_design, security_audit, data_analysis, doc_generation, test_framework
- **seungjeongwon**: saganwon 와 동일 (조정자)
- **byeongjo**: code_review, api_design, test_framework
- **hyeongjo**: code_review, security_audit, test_framework

### 특정 스킬을 최신 버전으로 갱신

```bash
python3 scripts/skill_manager.py update-remote \
  --agent hongmungwan \
  --name code_review

# 출력:
# ⏳ https://raw.githubusercontent.com/... 에서 다운로드 중...
# ✅ 스킬 code_review 가 hongmungwan 에 추가되었습니다
# ✅ 스킬이 갱신되었습니다
#    경로: /Users/xxx/.openclaw/workspace-hongmungwan/skills/code_review/SKILL.md
#    크기: 2156 바이트
```

### 특정 스킬 제거

```bash
python3 scripts/skill_manager.py remove-remote \
  --agent hongmungwan \
  --name code_review

# 출력:
# ✅ 스킬 code_review 가 hongmungwan 에서 제거되었습니다
```

---

## 칸반 UI 조작

### 칸반에서 원격 스킬 추가하기

1. http://localhost:7891 열기
2. 🔧 **스킬 설정** 패널로 진입
3. **➕ 원격 스킬 추가** 버튼 클릭
4. 양식 작성:
   - **Agent**: 드롭다운 목록에서 선택 (예: hongmungwan)
   - **스킬 이름**: 내부 ID 입력, 예: `code_review`
   - **원격 URL**: GitHub URL 붙여넣기, 예: `https://raw.githubusercontent.com/openclaw-ai/skills-hub/main/code_review/SKILL.md`
   - **한국어 설명**: 선택, 예: `코드 리뷰 능력`
5. **가져오기** 버튼 클릭
6. 1~2초 대기 후 ✅ 성공 알림 확인

### 추가된 스킬 관리

칸반 → 🔧 스킬 설정 → **원격 스킬** 탭에서:

- **조회**: 스킬 이름을 클릭하여 SKILL.md 내용 확인
- **갱신**: 🔄 클릭하여 출처 URL 에서 최신 버전을 다시 다운로드
- **삭제**: ✕ 클릭하여 로컬 사본 제거
- **URL 복사**: 다른 사람과 빠르게 공유

---

## 자체 스킬 저장소 만들기

### 디렉터리 구조

```
my-skills-hub/
├── code_review/
│   └── SKILL.md          # 코드 리뷰 능력
├── api_design/
│   └── SKILL.md          # API 설계 리뷰
├── data_analysis/
│   └── SKILL.md          # 데이터 분석
└── README.md
```

### SKILL.md 템플릿

```markdown
---
name: my_custom_skill
description: 짧은 설명
version: 1.0.0
tags: [tag1, tag2]
---

# 스킬 전체 이름

상세 설명...

## 입력

어떤 매개변수를 받는지 설명

## 처리 흐름

구체적인 단계...

## 출력 규격

출력 형식 설명
```

### GitHub 에 업로드

```bash
git init
git add .
git commit -m "Initial commit: my-skills-hub"
git remote add origin https://github.com/yourname/my-skills-hub
git push -u origin main
```

### 자체 스킬 가져오기

```bash
python3 scripts/skill_manager.py add-remote \
  --agent hongmungwan \
  --name my_skill \
  --source https://raw.githubusercontent.com/yourname/my-skills-hub/main/my_skill/SKILL.md \
  --description "내 맞춤 스킬"
```

---

## API 전체 참조

### POST /api/add-remote-skill

원격 스킬을 추가합니다.

**요청:**
```bash
curl -X POST http://localhost:7891/api/add-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "hongmungwan",
    "skillName": "code_review",
    "sourceUrl": "https://raw.githubusercontent.com/...",
    "description": "코드 리뷰"
  }'
```

**응답 (200):**
```json
{
  "ok": true,
  "message": "스킬 code_review 가 원격 출처에서 hongmungwan 에 추가되었습니다",
  "skillName": "code_review",
  "agentId": "hongmungwan",
  "source": "https://raw.githubusercontent.com/...",
  "localPath": "/Users/xxx/.openclaw/workspace-hongmungwan/skills/code_review/SKILL.md",
  "size": 2048,
  "addedAt": "2026-03-02T14:30:00Z"
}
```

### GET /api/remote-skills-list

모든 원격 스킬을 나열합니다.

```bash
curl http://localhost:7891/api/remote-skills-list
```

**응답:**
```json
{
  "ok": true,
  "remoteSkills": [
    {
      "skillName": "code_review",
      "agentId": "hongmungwan",
      "sourceUrl": "https://raw.githubusercontent.com/...",
      "description": "코드 리뷰 능력",
      "localPath": "/Users/xxx/.openclaw/workspace-hongmungwan/skills/code_review/SKILL.md",
      "addedAt": "2026-03-02T14:30:00Z",
      "lastUpdated": "2026-03-02T14:30:00Z",
      "status": "valid"
    }
  ],
  "count": 1,
  "listedAt": "2026-03-02T14:35:00Z"
}
```

### POST /api/update-remote-skill

원격 스킬을 최신 버전으로 갱신합니다.

```bash
curl -X POST http://localhost:7891/api/update-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "hongmungwan",
    "skillName": "code_review"
  }'
```

### DELETE /api/remove-remote-skill

원격 스킬을 제거합니다.

```bash
curl -X POST http://localhost:7891/api/remove-remote-skill \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "hongmungwan",
    "skillName": "code_review"
  }'
```

---

## 문제 해결

### Q: 다운로드 실패, "Connection timeout" 표시

**A:** 네트워크 연결과 URL 유효성 확인

```bash
curl -I https://raw.githubusercontent.com/...
# HTTP/1.1 200 OK 반환되어야 함
```

### Q: 파일 형식이 유효하지 않음

**A:** SKILL.md 가 YAML frontmatter 로 시작하는지 확인

```markdown
---
name: skill_name
description: 설명
---

# 본문 시작...
```

### Q: 가져온 후 스킬이 보이지 않음

**A:** 칸반을 새로 고치거나 Agent 설정이 올바른지 확인

```bash
# Agent 존재 여부 확인
python3 scripts/skill_manager.py list-remote

# 로컬 파일 확인
ls -la ~/.openclaw/workspace-hongmungwan/skills/
```

---

## 더 많은 정보

- 📚 [전체 가이드](remote-skills-guide.md)
- 🏛️ [아키텍처 문서](task-dispatch-architecture.md)
- 🤝 [프로젝트 기여](../CONTRIBUTING.md)

