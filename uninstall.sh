#!/bin/bash
# ════════════════════════════════════════════════════════════
# 3사6조 · OpenClaw Multi-Agent System 원클릭 제거 스크립트
# ════════════════════════════════════════════════════════════
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OC_HOME="$HOME/.openclaw"
OC_CFG="$OC_HOME/openclaw.json"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

banner() {
  echo ""
  echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║  🏛️  3사6조 · 제거 마법사                  ║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
  echo ""
}

log()   { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
info()  { echo -e "${BLUE}ℹ️  $1${NC}"; }

# ── Step 0: 확인 ────────────────────────────────────────────
check_env() {
  info "환경 확인 중..."
  if ! command -v python3 &>/dev/null; then
    warn "python3를 찾을 수 없습니다. 설정 항목 정리를 건너뜁니다"
  fi

  echo ""
  echo -e "${YELLOW}3사6조 시스템을 제거하고 관련 Agent 데이터를 정리하시겠습니까？${NC}"
  read -p "(y/N) " -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    info "제거가 취소되었습니다"
    exit 0
  fi
}

# ── Step 1: 실행 중인 서비스 중지 ────────────────────────────────
stop_services() {
  info "관련 프로세스 중지 시도 중..."

  if pgrep -f "scripts/run_loop.sh" > /dev/null 2>&1; then
    pkill -f "scripts/run_loop.sh" || warn "run_loop.sh를 자동으로 중지할 수 없습니다"
    log "run_loop.sh 중지 시도됨"
  fi

  if pgrep -f "python.*dashboard/server.py" > /dev/null 2>&1; then
    pkill -f "python.*dashboard/server.py" || warn "dashboard/server.py를 자동으로 중지할 수 없습니다"
    log "dashboard/server.py 중지 시도됨"
  fi
}

# ── Step 2: OpenClaw 등록 설정 정리 ──────────────────────────────
unregister_agents() {
  info "OpenClaw에서 3사6조 Agents 등록 정보 제거 중..."

  if [ ! -f "$OC_CFG" ]; then
    warn "openclaw.json을 찾을 수 없습니다. 설정 정리를 건너뜁니다"
    return
  fi

  cp "$OC_CFG" "$OC_CFG.bak.pre-uninstall-$(date +%Y%m%d-%H%M%S)"
  log "현재 설정 백업됨"

  python3 << 'PYEOF'
import json, pathlib

cfg_path = pathlib.Path.home() / '.openclaw' / 'openclaw.json'
if not cfg_path.exists():
    print("  openclaw.json이 존재하지 않습니다.")
    exit(0)

try:
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
except Exception as e:
    print(f"  openclaw.json 파싱 실패: {e}")
    exit(1)

AGENTS_TO_REMOVE = {
    "seja", "hongmungwan", "saganwon", "seungjeongwon",
    "hojo", "yejo", "byeongjo", "hyeongjo", "gongjo",
    "ijo", "jobocheong"
}

agents_list = cfg.get('agents', {}).get('list', [])
new_list = [a for a in agents_list if a.get('id') not in AGENTS_TO_REMOVE]
removed_count = len(agents_list) - len(new_list)

if 'agents' in cfg:
    cfg['agents']['list'] = new_list
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  {removed_count}개 Agent의 등록 정보가 성공적으로 제거되었습니다")
PYEOF

  log "등록 정보 정리 완료"
}

# ── Step 3: 워크스페이스 디렉토리 삭제 ─────────────────────────────────
remove_workspaces() {
  info "Agent 워크스페이스 디렉토리 삭제 중..."

  AGENTS=(seja hongmungwan saganwon seungjeongwon hojo yejo byeongjo hyeongjo gongjo ijo jobocheong)
  removed=0
  for agent in "${AGENTS[@]}"; do
    ws="$OC_HOME/workspace-$agent"
    if [ -d "$ws" ]; then
      rm -rf "$ws"
      removed=$((removed+1))
    fi
  done

  log "워크스페이스 디렉토리 $removed개가 성공적으로 정리되었습니다"
}

# ── Step 4: 로컬 데이터 캐시 삭제 ────────────────────────────────────
remove_data() {
  info "로컬 data 캐시 삭제 중..."

  echo -e "${YELLOW}프로젝트 내 data 디렉토리 및 생성된 데이터를 삭제하시겠습니까？${NC}"
  read -p "(y/N) " -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$REPO_DIR/data" ]; then
      rm -rf "$REPO_DIR/data"
      log "$REPO_DIR/data 삭제됨"
    else
      warn "$REPO_DIR/data가 존재하지 않습니다"
    fi
  else
    info "기존 data 디렉토리 유지"
  fi
}

# ── Step 5: Gateway 재시작 ────────────────────────────────────────
restart_gateway() {
  info "설정을 적용하기 위해 OpenClaw Gateway 재시작 중..."
  if command -v openclaw &>/dev/null; then
    if openclaw gateway restart 2>/dev/null; then
      log "Gateway 재시작 성공"
    else
      warn "Gateway 재시작 실패, 수동으로 재시작하세요: openclaw gateway restart"
    fi
  else
    warn "openclaw 명령줄 도구를 찾을 수 없습니다. Gateway 재시작을 건너뜁니다"
  fi
}

# ── Main ────────────────────────────────────────────────────
banner
check_env
stop_services
unregister_agents
remove_workspaces
remove_data
restart_gateway

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅  3사6조 제거 완료！                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""
