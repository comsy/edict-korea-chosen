# 사례 2: 코드 보안 점검

> **지시**: FastAPI 코드의 보안성을 점검하고, 문제 목록과 수정 방안을 산출하라

---

## 📜 지시 (원본 명령)

```
다음 FastAPI 코드의 보안성을 점검하라. 중점 사항은:
1. 인증·인가 취약점
2. SQL 주입 위험
3. 입력 검증
4. 민감 정보 누출
문제 목록(심각도 순)과 수정 코드를 제시하라.

[첨부: app/main.py, app/models.py, app/auth.py — 합계 320줄]
```

**지시 ID**: `JJC-20260221-007`
**어명 하달 시각**: 2026-02-21 14:30:00

---

## 📋 홍문관 기획

> 지시 접수 후 30초 이내에 기획 완료

**기획안:**

| # | 하위 작업 | 배정 부서 | 설명 |
|---|--------|----------|------|
| 1 | 코드 보안 스캔 | ⚔️ 병조 | 파일별 점검, 보안 문제 표식 |
| 2 | 컴플라이언스 및 모범 관례 점검 | ⚖️ 형조 | OWASP Top 10 대조 점검 |
| 3 | 수정 방안 산출 | ⚔️ 병조 | 문제별 수정 코드 제시 |

**예상 소요**: 12분
**예상 토큰**: ~9,000

---

## 🔍 사간원 심의

> ⏱️ 심의 소요 18초

### 승인 ✅ (1차 통과)

**사간원 비답:** *"기획안 합리적이다. 병조는 엔지니어링 측 점검을, 형조는 컴플라이언스 측 점검을 맡아 분담이 명확하다. 다만 형조는 OWASP 항목별 대조표를 반드시 작성해야 하며, '대체로 합규'라는 식의 모호한 결론은 허용하지 않는다. 승인."*

---

## ⚔️ 각 조 집행 결과

### 병조 · 코드 보안 스캔 (소요 5분)

**스캔 결과 6건 발견:**

| # | 심각도 | 파일 | 문제 |
|---|--------|------|------|
| 1 | 🔴 치명 | auth.py:23 | JWT secret이 소스 코드에 하드코딩됨 |
| 2 | 🔴 치명 | main.py:45 | SQL 쿼리가 f-string 결합 방식, 주입 위험 |
| 3 | 🟠 높음 | main.py:67 | 사용자 입력 길이 제한 없음, DoS 가능 |
| 4 | 🟠 높음 | auth.py:41 | 토큰 만료 시간이 30일로 과도하게 김 |
| 5 | 🟡 중간 | main.py:12 | CORS가 `allow_origins=["*"]` 로 설정 |
| 6 | 🟡 중간 | models.py:8 | 비밀번호 필드가 response_model에서 제외되지 않음 |

### 형조 · OWASP 컴플라이언스 점검 (소요 4분)

**OWASP Top 10 항목별 대조:**

| OWASP 번호 | 카테고리 | 상태 | 설명 |
|-----------|------|------|------|
| A01 | Broken Access Control | 🟠 부분 합규 | JWT는 있으나 역할 단위 검증 부족 |
| A02 | Cryptographic Failures | 🔴 미합규 | Secret 하드코딩 |
| A03 | Injection | 🔴 미합규 | SQL 결합 |
| A04 | Insecure Design | ✅ 합규 | 전체 구조는 합리적 |
| A05 | Security Misconfiguration | 🟡 개선 필요 | CORS 과다 허용 |
| A06 | Vulnerable Components | ✅ 합규 | 의존성 버전 양호 |
| A07 | Auth Failures | 🟠 부분 합규 | 토큰 만료 시간 과다 |
| A08 | Data Integrity | ✅ 합규 | — |
| A09 | Logging Failures | 🟡 개선 필요 | 보안 이벤트 로깅 부재 |
| A10 | SSRF | ✅ 합규 | 외부 요청 없음 |

**형조 결론:** 10항 중 6항이 처리 대상이며, 그중 2항(A02, A03)은 미합규로 즉시 수정이 필요합니다.

### 병조 · 수정 코드 (소요 3분)

```python
# 수정 #1: auth.py — JWT secret을 환경 변수에서 읽기
import os
JWT_SECRET = os.environ["JWT_SECRET"]  # 더 이상 하드코딩하지 않음

# 수정 #2: main.py — 매개변수화 쿼리 사용
from sqlalchemy import text
result = db.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})

# 수정 #3: main.py — 입력 길이 제한 추가
from pydantic import Field
class UserInput(BaseModel):
    name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=255)

# 수정 #4: auth.py — 토큰 만료 시간 단축
ACCESS_TOKEN_EXPIRE = timedelta(hours=1)  # 30일에서 1시간으로 변경

# 수정 #5: main.py — CORS 범위 좁히기
app.add_middleware(CORSMiddleware, allow_origins=["https://yourdomain.com"])

# 수정 #6: models.py — 비밀번호 필드 제외
class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    # password 필드는 본 model에 포함하지 않음
```

---

## 📮 최종 결과 보고 (승정원 취합)

**결과 보고 ID**: `JJC-20260221-007`
**총 소요**: 14분 (기획 1 + 심의 0.5 + 집행 12.5)
**총 토큰**: 8,200

### 집행 요약

320줄 분량의 FastAPI 코드에 대해 보안 점검을 마쳤습니다. 보안 문제 6건(치명 2 / 높음 2 / 중간 2)을 발견했고, OWASP Top 10 중 2항이 미합규였습니다. 6건 전부에 대한 수정 코드가 제공되었습니다.

사간원은 1차에서 곧바로 승인했고, 병조와 형조의 분담이 명확했습니다. 병조는 코드 단위의 스캔과 수정을, 형조는 컴플라이언스 프레임워크 대조를 담당했습니다.

### 권장 우선순위

1. **즉시 수정**: JWT secret 하드코딩 + SQL 주입 (배포 전 반드시 해소)
2. **이번 주 내**: 입력 길이 제한 + 토큰 만료 시간
3. **다음 이터레이션**: CORS 범위 축소 + 비밀번호 필드 노출

---

*본 사례는 실제 운영 기록을 바탕으로 정리되었으며, 코드 내용은 익명화 처리되었습니다.*
