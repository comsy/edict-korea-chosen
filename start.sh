#!/bin/bash
# ══════════════════════════════════════════════════════════════
# 3사6조 · 원클릭 시작 스크립트
# 대시보드 서버 + 데이터 새로고침 루프를 동시에 시작
# ══════════════════════════════════════════════════════════════

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

# Python 확인
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}❌ python3를 찾을 수 없습니다. Python 3.9+를 먼저 설치해주세요${NC}"
  exit 1
fi

# data 디렉토리가 존재하는지 확인
mkdir -p "$REPO_DIR/data"

# 필수 데이터 파일 초기화 (없는 경우)
for f in live_status.json agent_config.json model_change_log.json sync_status.json; do
  [ ! -f "$REPO_DIR/data/$f" ] && echo '{}' > "$REPO_DIR/data/$f"
done
[ ! -f "$REPO_DIR/data/pending_model_changes.json" ] && echo '[]' > "$REPO_DIR/data/pending_model_changes.json"
[ ! -f "$REPO_DIR/data/tasks_source.json" ] && echo '[]' > "$REPO_DIR/data/tasks_source.json"
[ ! -f "$REPO_DIR/data/tasks.json" ] && echo '[]' > "$REPO_DIR/data/tasks.json"
[ ! -f "$REPO_DIR/data/officials.json" ] && echo '[]' > "$REPO_DIR/data/officials.json"
[ ! -f "$REPO_DIR/data/officials_stats.json" ] && echo '{}' > "$REPO_DIR/data/officials_stats.json"

cleanup() {
  echo ""
  echo -e "${YELLOW}서비스를 종료하는 중...${NC}"
  kill $SERVER_PID $LOOP_PID 2>/dev/null
  wait $SERVER_PID $LOOP_PID 2>/dev/null
  echo -e "${GREEN}✅ 종료되었습니다${NC}"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  🏛️  3사6조 · 서비스 시작 중               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# 데이터 새로고침 루프 시작 (백그라운드)
if command -v openclaw &>/dev/null; then
  echo -e "${GREEN}▶ 데이터 새로고침 루프 시작...${NC}"
  bash scripts/run_loop.sh &
  LOOP_PID=$!
else
  echo -e "${YELLOW}⚠️  OpenClaw CLI가 감지되지 않았습니다. 데이터 새로고침 루프를 건너뜁니다${NC}"
  echo -e "${YELLOW}   대시보드가 읽기 전용 모드로 실행됩니다 (기존 데이터 사용)${NC}"
  LOOP_PID=""
fi

# 대시보드 서버 시작
echo -e "${GREEN}▶ 대시보드 서버 시작...${NC}"
python3 dashboard/server.py &
SERVER_PID=$!

sleep 1
echo ""
echo -e "${GREEN}✅ 서비스가 시작되었습니다!${NC}"
echo -e "   대시보드 주소: ${BLUE}http://127.0.0.1:7891${NC}"
echo -e "   ${YELLOW}Ctrl+C${NC}를 눌러 모든 서비스 종료"
echo ""

# 브라우저 자동 열기 시도
if command -v open &>/dev/null; then
  open http://127.0.0.1:7891
elif command -v xdg-open &>/dev/null; then
  xdg-open http://127.0.0.1:7891
fi

# 프로세스 중 하나가 종료될 때까지 대기
wait $SERVER_PID $LOOP_PID 2>/dev/null
