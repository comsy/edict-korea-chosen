#!/usr/bin/env python3
"""kanban_update.py 전체 흐름 E2E 테스트 (정제+생성+전이)

pytest 또는 python3로 직접 실행 가능.
"""
import sys, os, json, pathlib, pytest

# scripts 디렉토리로 이동 (file_lock 의존성)
_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'scripts')
os.chdir(_SCRIPTS_DIR)
sys.path.insert(0, '.')

from kanban_update import (
    _sanitize_title, _sanitize_remark, _is_valid_task_title,
    cmd_create, cmd_flow, cmd_state, cmd_done, load, TASKS_FILE
)

# data 디렉토리와 tasks_source.json 존재 확인 (CI 환경 대비)
data_dir = TASKS_FILE.parent
if data_dir.exists() and not data_dir.is_dir():
    data_dir.unlink()
data_dir.mkdir(parents=True, exist_ok=True)
if not TASKS_FILE.exists():
    TASKS_FILE.write_text('[]')


def _get_task(tid):
    return next((x for x in load() if x['id'] == tid), None)


@pytest.fixture(autouse=True)
def _backup_and_restore():
    """각 테스트 전 데이터 백업, 테스트 후 복원 및 테스트 작업 정리."""
    backup = TASKS_FILE.read_text()
    yield
    TASKS_FILE.write_text(backup)
    tasks = json.loads(TASKS_FILE.read_text())
    tasks = [t for t in tasks if not t.get('id', '').startswith('JJC-TEST-')]
    TASKS_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2))


# ── TEST 1: 더러운 제목(파일 경로+Conversation 포함)은 정제 후 생성
def test_dirty_title_cleaned():
    cmd_create('JJC-TEST-E2E-01',
        '전면 점검/Users/bingsen/clawd/openclaw-sansheng-liubu/이 프로젝트\nConversation info (xxx)',
        'HongmungwanDraft', '홍문관', '홍문관제학',
        '하지(자동 사전 생성): 전면 점검/Users/bingsen/clawd/프로젝트')
    t = _get_task('JJC-TEST-E2E-01')
    assert t is not None, "작업이 생성되어야 함"
    assert '/Users' not in t['title'], f"제목에 경로가 없어야 함: {t['title']}"
    assert 'Conversation' not in t['title'], f"제목에 Conversation이 없어야 함: {t['title']}"
    assert '자동 사전 생성' not in t['flow_log'][0]['remark'], f"remark에 자동 사전 생성이 없어야 함: {t['flow_log'][0]['remark']}"
    assert '/Users' not in t['flow_log'][0]['remark'], f"remark에 경로가 없어야 함: {t['flow_log'][0]['remark']}"


# ── TEST 2: 순수 파일 경로 제목은 거부
def test_pure_path_rejected():
    cmd_create('JJC-TEST-E2E-02', '/Users/bingsen/clawd/openclaw-sansheng-liubu/', 'HongmungwanDraft', '홍문관', '홍문관제학')
    assert _get_task('JJC-TEST-E2E-02') is None, "순수 경로 제목은 거부되어야 함"


# ── TEST 3: 정상 제목은 정상 생성
def test_normal_title():
    cmd_create('JJC-TEST-E2E-03', '산업 데이터 분석 대형 모델 응용 조사', 'HongmungwanDraft', '홍문관', '홍문관제학', '세자 지시 정리')
    t = _get_task('JJC-TEST-E2E-03')
    assert t is not None, "정상 작업은 생성되어야 함"
    assert t['title'] == '산업 데이터 분석 대형 모델 응용 조사', f"제목이 완전히 보존되어야 함: {t['title']}"


# ── TEST 4: flow remark 정제
def test_flow_remark_cleaned():
    cmd_create('JJC-TEST-E2E-04', '산업 데이터 분석 대형 모델 응용 조사', 'HongmungwanDraft', '홍문관', '홍문관제학')
    cmd_flow('JJC-TEST-E2E-04', '세자', '홍문관', '지시 전달: /Users/bingsen/clawd/xxx 프로젝트 검토 Conversation blah')
    t = _get_task('JJC-TEST-E2E-04')
    assert t is not None
    last_flow = t['flow_log'][-1]
    assert '/Users' not in last_flow['remark'], f"remark에 경로가 없어야 함: {last_flow['remark']}"
    assert 'Conversation' not in last_flow['remark'], f"remark에 Conversation이 없어야 함: {last_flow['remark']}"


# ── TEST 5: 너무 짧은 제목 거부
def test_short_title_rejected():
    cmd_create('JJC-TEST-E2E-05', '알겠어', 'HongmungwanDraft', '홍문관', '홍문관제학')
    assert _get_task('JJC-TEST-E2E-05') is None, "짧은 제목은 거부되어야 함"


# ── TEST 6: 전지/하지 등 접두어 제거
def test_prefix_stripped():
    cmd_create('JJC-TEST-E2E-06', '전지: 지능형 에이전트 아키텍처 기술 블로그 작성', 'HongmungwanDraft', '홍문관', '홍문관제학')
    t = _get_task('JJC-TEST-E2E-06')
    assert t is not None, "작업이 생성되어야 함"
    assert not t['title'].startswith('전지'), f"접두어가 제거되어야 함: {t['title']}"


# ── TEST 7: state 갱신 + org 자동 연동
def test_state_update():
    cmd_create('JJC-TEST-E2E-07', '상태 갱신 및 부서 연동 기능 테스트', 'HongmungwanDraft', '홍문관', '홍문관제학')
    cmd_state('JJC-TEST-E2E-07', 'SaganwonFinalReview', '방안을 사간원 심의에 제출')
    t = _get_task('JJC-TEST-E2E-07')
    assert t is not None
    assert t['state'] == 'SaganwonFinalReview', f"state가 SaganwonFinalReview여야 함: {t['state']}"
    assert t['org'] == '사간원', f"org가 사간원이어야 함: {t['org']}"


# ── TEST 8: done 호출 시 InProgress → FinalReview 전이 (승정원 취합 심사 대기)
def test_done():
    cmd_create('JJC-TEST-E2E-08', '작업 완료 상태 표시 기능 테스트', 'HongmungwanDraft', '홍문관', '홍문관제학')
    # 집행 단계까지 진행: HongmungwanDraft → SaganwonFinalReview → SeungjeongwonAssigned → InProgress
    cmd_state('JJC-TEST-E2E-08', 'SaganwonFinalReview', '사간원 심의')
    cmd_state('JJC-TEST-E2E-08', 'SeungjeongwonAssigned', '승정원 배분')
    cmd_state('JJC-TEST-E2E-08', 'InProgress', '집행 시작')
    cmd_done('JJC-TEST-E2E-08', '/tmp/output.md', '작업 완료')
    t = _get_task('JJC-TEST-E2E-08')
    assert t is not None
    assert t['state'] == 'FinalReview', f"state가 FinalReview여야 함: {t['state']}"


# ── TEST 9: 터미널 상태(Cancelled) 작업은 덮어쓸 수 없음
def test_done_not_overwritable():
    cmd_create('JJC-TEST-E2E-09', '완료된 작업 덮어쓰기 방지 기능 테스트', 'HongmungwanDraft', '홍문관', '홍문관제학')
    # Cancelled 는 터미널 상태이며 HongmungwanDraft → Cancelled 직접 전이가 허용됨
    cmd_state('JJC-TEST-E2E-09', 'Cancelled', '작업 취소')
    cmd_create('JJC-TEST-E2E-09', '취소된 작업 제목 덮어쓰기 시도', 'HongmungwanDraft', '홍문관', '홍문관제학')
    t = _get_task('JJC-TEST-E2E-09')
    assert t is not None
    assert t['state'] == 'Cancelled', f"여전히 Cancelled여야 함 (덮어쓰기 차단): {t['state']}"
    assert '덮어쓰기 시도' not in t['title'], f"제목이 덮어써지지 않아야 함: {t['title']}"


# ── python3 tests/test_e2e_kanban.py 직접 실행 지원
if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
