#!/bin/bash
# ══════════════════════════════════════════════════════════════
# 3사6조 · 통합 서비스 관리 스크립트
# 사용법: ./edict.sh {start|stop|status|restart|logs}
# ══════════════════════════════════════════════════════════════

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDDIR="$REPO_DIR/.pids"
LOGDIR="$REPO_DIR/logs"

SERVER_PIDFILE="$PIDDIR/server.pid"
LOOP_PIDFILE="$PIDDIR/loop.pid"
SERVER_LOG="$LOGDIR/server.log"
LOOP_LOG="$LOGDIR/loop.log"

# 환경 변수로 오버라이드 가능한 설정
DASHBOARD_HOST="${EDICT_DASHBOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${EDICT_DASHBOARD_PORT:-7891}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

# ── 유틸리티 함수 ──

_ensure_dirs() {
  mkdir -p "$PIDDIR" "$LOGDIR" "$REPO_DIR/data"
  # 필수 데이터 파일 초기화
  for f in live_status.json agent_config.json model_change_log.json sync_status.json; do
    [ ! -f "$REPO_DIR/data/$f" ] && echo '{}' > "$REPO_DIR/data/$f"
  done
  [ ! -f "$REPO_DIR/data/pending_model_changes.json" ] && echo '[]' > "$REPO_DIR/data/pending_model_changes.json"
  [ ! -f "$REPO_DIR/data/tasks_source.json" ] && echo '[]' > "$REPO_DIR/data/tasks_source.json"
  [ ! -f "$REPO_DIR/data/tasks.json" ] && echo '[]' > "$REPO_DIR/data/tasks.json"
  [ ! -f "$REPO_DIR/data/officials.json" ] && echo '[]' > "$REPO_DIR/data/officials.json"
  [ ! -f "$REPO_DIR/data/officials_stats.json" ] && echo '{}' > "$REPO_DIR/data/officials_stats.json"
}

_is_running() {
  local pidfile="$1"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid=$(cat "$pidfile" 2>/dev/null)
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    # PID 파일이 존재하지만 프로세스가 죽은 경우, 정리
    rm -f "$pidfile"
  fi
  return 1
}

_get_pid() {
  local pidfile="$1"
  if [[ -f "$pidfile" ]]; then
    cat "$pidfile" 2>/dev/null
  fi
}

# ── 시작 ──

do_start() {
  _ensure_dirs

  if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ python3를 찾을 수 없습니다. Python 3.9+를 먼저 설치해주세요${NC}"
    exit 1
  fi

  echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║  🏛️  3사6조 · 서비스 시작 중               ║${NC}"
  echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
  echo ""

  # 실행 중인지 확인
  local already=0
  if _is_running "$SERVER_PIDFILE"; then
    echo -e "${YELLOW}⚠️  대시보드 서버가 이미 실행 중입니다 (PID=$(_get_pid "$SERVER_PIDFILE"))${NC}"
    already=$((already+1))
  fi
  if _is_running "$LOOP_PIDFILE"; then
    echo -e "${YELLOW}⚠️  데이터 새로고침 루프가 이미 실행 중입니다 (PID=$(_get_pid "$LOOP_PIDFILE"))${NC}"
    already=$((already+1))
  fi
  if [[ $already -eq 2 ]]; then
    echo -e "${YELLOW}모든 서비스가 이미 실행 중입니다. 재시작하려면: $0 restart${NC}"
    return 0
  fi

  # 데이터 새로고침 루프 시작 (백그라운드)
  if ! _is_running "$LOOP_PIDFILE"; then
    if command -v openclaw &>/dev/null; then
      echo -e "${GREEN}▶ 데이터 새로고침 루프 시작...${NC}"
      nohup bash "$REPO_DIR/scripts/run_loop.sh" >> "$LOOP_LOG" 2>&1 &
      echo $! > "$LOOP_PIDFILE"
      echo -e "  PID=$(_get_pid "$LOOP_PIDFILE")  로그: ${BLUE}$LOOP_LOG${NC}"
    else
      echo -e "${YELLOW}⚠️  OpenClaw CLI가 감지되지 않았습니다. 데이터 새로고침 루프를 건너뜁니다${NC}"
      echo -e "${YELLOW}   대시보드가 읽기 전용 모드로 실행됩니다 (기존 데이터 사용)${NC}"
    fi
  fi

  # 대시보드 서버 시작 (백그라운드)
  if ! _is_running "$SERVER_PIDFILE"; then
    echo -e "${GREEN}▶ 대시보드 서버 시작...${NC}"
    nohup python3 "$REPO_DIR/dashboard/server.py" \
      --host "$DASHBOARD_HOST" --port "$DASHBOARD_PORT" \
      >> "$SERVER_LOG" 2>&1 &
    echo $! > "$SERVER_PIDFILE"
    echo -e "  PID=$(_get_pid "$SERVER_PIDFILE")  로그: ${BLUE}$SERVER_LOG${NC}"
  fi

  sleep 1
  echo ""
  if _is_running "$SERVER_PIDFILE"; then
    echo -e "${GREEN}✅ 서비스가 시작되었습니다!${NC}"
    echo -e "   대시보드 주소: ${BLUE}http://${DASHBOARD_HOST}:${DASHBOARD_PORT}${NC}"
  else
    echo -e "${RED}❌ 대시보드 서버 시작 실패, 로그를 확인하세요: $SERVER_LOG${NC}"
    exit 1
  fi
}

# ── 중지 ──

do_stop() {
  echo -e "${YELLOW}서비스를 종료하는 중...${NC}"
  local stopped=0

  for label_pid in "대시보드 서버:$SERVER_PIDFILE" "데이터 새로고침 루프:$LOOP_PIDFILE"; do
    local label="${label_pid%%:*}"
    local pidfile="${label_pid#*:}"
    if _is_running "$pidfile"; then
      local pid
      pid=$(_get_pid "$pidfile")
      kill "$pid" 2>/dev/null
      # 최대 5초 대기
      for _ in $(seq 1 10); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
      done
      # 여전히 실행 중이면 강제 종료
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null
      fi
      rm -f "$pidfile"
      echo -e "  ✅ ${label} (PID=$pid) 종료됨"
      stopped=$((stopped+1))
    fi
  done

  if [[ $stopped -eq 0 ]]; then
    echo -e "${YELLOW}   실행 중인 서비스가 없습니다${NC}"
  else
    echo -e "${GREEN}✅ 모든 서비스가 종료되었습니다${NC}"
  fi
}

# ── 상태 ──

do_status() {
  echo -e "${BLUE}🏛️  3사6조 · 서비스 상태${NC}"
  echo ""

  for label_pid in "대시보드 서버:$SERVER_PIDFILE" "데이터 새로고침 루프:$LOOP_PIDFILE"; do
    local label="${label_pid%%:*}"
    local pidfile="${label_pid#*:}"
    if _is_running "$pidfile"; then
      local pid
      pid=$(_get_pid "$pidfile")
      echo -e "  ${GREEN}●${NC} ${label}  PID=$pid  ${GREEN}실행 중${NC}"
    else
      echo -e "  ${RED}○${NC} ${label}  ${RED}실행 중이 아님${NC}"
    fi
  done

  echo ""
  # 대시보드가 실행 중이면 healthz 시도
  if _is_running "$SERVER_PIDFILE"; then
    local health
    if health=$(python3 -c "
import urllib.request, json, sys
try:
    r = urllib.request.urlopen('http://${DASHBOARD_HOST}:${DASHBOARD_PORT}/healthz', timeout=3)
    d = json.loads(r.read())
    print('healthy' if d.get('status')=='ok' else 'unhealthy')
except Exception:
    print('unreachable')
" 2>/dev/null); then
      case "$health" in
        healthy)    echo -e "  상태 확인: ${GREEN}✅ 정상${NC}" ;;
        unhealthy)  echo -e "  상태 확인: ${YELLOW}⚠️  비정상${NC}" ;;
        *)          echo -e "  상태 확인: ${RED}❌ 연결 불가${NC}" ;;
      esac
    fi
    echo -e "  대시보드 주소: ${BLUE}http://${DASHBOARD_HOST}:${DASHBOARD_PORT}${NC}"
  fi
}

# ── 로그 ──

do_logs() {
  local target="${1:-all}"
  case "$target" in
    server)  tail -f "$SERVER_LOG" ;;
    loop)    tail -f "$LOOP_LOG" ;;
    all)     tail -f "$SERVER_LOG" "$LOOP_LOG" ;;
    *)       echo "사용법: $0 logs [server|loop|all]"; exit 1 ;;
  esac
}

# ── 메인 진입점 ──

case "${1:-}" in
  start)   do_start ;;
  stop)    do_stop ;;
  restart) do_stop; sleep 1; do_start ;;
  status)  do_status ;;
  logs)    do_logs "${2:-all}" ;;
  *)
    echo "사용법: $0 {start|stop|restart|status|logs}"
    echo ""
    echo "명령어:"
    echo "  start     모든 서비스 시작 (대시보드 + 데이터 새로고침)"
    echo "  stop      모든 서비스 중지"
    echo "  restart   모든 서비스 재시작"
    echo "  status    실행 상태 확인"
    echo "  logs      로그 보기 (logs [server|loop|all])"
    echo ""
    echo "환경 변수:"
    echo "  EDICT_DASHBOARD_HOST   수신 주소 (기본값: 127.0.0.1)"
    echo "  EDICT_DASHBOARD_PORT   수신 포트 (기본값: 7891)"
    exit 1
    ;;
esac
