#!/bin/bash
# ══════════════════════════════════════════════════════════════
# 3사6조 · OpenClaw Multi-Agent System 원클릭 설치 스크립트
# ══════════════════════════════════════════════════════════════
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OC_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
OC_CFG="$OC_HOME/openclaw.json"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

banner() {
  echo ""
  echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║  🏛️  3사6조 · OpenClaw Multi-Agent    ║${NC}"
  echo -e "${BLUE}║       설치 마법사                            ║${NC}"
  echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
  echo ""
}

log()   { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }
info()  { echo -e "${BLUE}ℹ️  $1${NC}"; }

# ── Step 0: 의존성 확인 ──────────────────────────────────────────
check_deps() {
  info "의존성 확인 중..."
  
  if ! command -v openclaw &>/dev/null; then
    error "openclaw CLI를 찾을 수 없습니다. 먼저 OpenClaw를 설치하세요: https://openclaw.ai"
    exit 1
  fi
  log "OpenClaw CLI: $(openclaw --version 2>/dev/null || echo 'OK')"

  if ! command -v python3 &>/dev/null; then
    error "python3를 찾을 수 없습니다"
    exit 1
  fi
  log "Python3: $(python3 --version)"

  if [ ! -f "$OC_CFG" ]; then
    error "openclaw.json을 찾을 수 없습니다. 먼저 openclaw를 실행하여 초기화하세요."
    exit 1
  fi
  log "openclaw.json: $OC_CFG"
}

# ── Step 0.5: 기존 Agent 데이터 백업 ──────────────────────────────
backup_existing() {
  AGENTS_DIR="$OC_HOME"
  BACKUP_DIR="$OC_HOME/backups/pre-install-$(date +%Y%m%d-%H%M%S)"
  HAS_EXISTING=false

  # 기존 워크스페이스 확인
  for d in "$AGENTS_DIR"/workspace-*/; do
    if [ -d "$d" ]; then
      HAS_EXISTING=true
      break
    fi
  done

  if $HAS_EXISTING; then
    info "기존 Agent 워크스페이스 감지, 자동 백업 중..."
    mkdir -p "$BACKUP_DIR"

    # 모든 워크스페이스 디렉토리 백업
    for d in "$AGENTS_DIR"/workspace-*/; do
      if [ -d "$d" ]; then
        ws_name=$(basename "$d")
        cp -R "$d" "$BACKUP_DIR/$ws_name"
      fi
    done

    # openclaw.json 백업
    if [ -f "$OC_CFG" ]; then
      cp "$OC_CFG" "$BACKUP_DIR/openclaw.json"
    fi

    # agents 디렉토리 백업 (에이전트 등록 정보)
    if [ -d "$AGENTS_DIR/agents" ]; then
      cp -R "$AGENTS_DIR/agents" "$BACKUP_DIR/agents"
    fi

    log "백업 완료: $BACKUP_DIR"
    info "복원이 필요한 경우: cp -R $BACKUP_DIR/workspace-* $AGENTS_DIR/"
  fi
}

# ── Step 1: 워크스페이스 생성 ──────────────────────────────────
create_workspaces() {
  info "Agent 워크스페이스 생성 중..."
  
  AGENTS=(seja hongmungwan saganwon seungjeongwon hojo yejo byeongjo hyeongjo gongjo ijo jobocheong)
  for agent in "${AGENTS[@]}"; do
    ws="$OC_HOME/workspace-$agent"
    mkdir -p "$ws/skills"
    if [ -f "$REPO_DIR/agents/$agent/SOUL.md" ]; then
      if [ -f "$ws/SOUL.md" ]; then
        # 기존 SOUL.md가 있으면 백업 후 덮어쓰기
        cp "$ws/SOUL.md" "$ws/SOUL.md.bak.$(date +%Y%m%d-%H%M%S)"
        warn "기존 SOUL.md 백업됨 → $ws/SOUL.md.bak.*"
      fi
      sed "s|__REPO_DIR__|$REPO_DIR|g" "$REPO_DIR/agents/$agent/SOUL.md" > "$ws/SOUL.md"
    fi
    log "워크스페이스 생성됨: $ws"
  done

  # 공통 AGENTS.md (작업 프로토콜)
  for agent in "${AGENTS[@]}"; do
    cat > "$OC_HOME/workspace-$agent/AGENTS.md" << 'AGENTS_EOF'
# AGENTS.md · 작업 프로토콜

1. 임무를 받으면 "지침을 받았습니다"라고 먼저 회신합니다.
2. 출력에는 반드시 다음을 포함합니다: 임무 ID, 결과, 증거/파일 경로, 차단 항목.
3. 협업이 필요한 경우, 상서성을 통해 파견을 요청하며 부서 간 직접 연결하지 않습니다.
4. 삭제/외부 전송 작업은 명시적으로 표시하고 승인을 기다립니다.
AGENTS_EOF
  done
}

# ── Step 2: Agent 등록 ─────────────────────────────────────
register_agents() {
  info "3사6조 Agents 등록 중..."

  # 설정 백업
  cp "$OC_CFG" "$OC_CFG.bak.sansheng-$(date +%Y%m%d-%H%M%S)"
  log "설정 백업됨: $OC_CFG.bak.*"

  python3 << 'PYEOF'
import json, os as _os, pathlib, sys

oc_home = pathlib.Path(_os.environ.get('OPENCLAW_HOME', str(pathlib.Path.home() / '.openclaw'))).expanduser()
cfg_path = oc_home / 'openclaw.json'
cfg = json.loads(cfg_path.read_text())

AGENTS = [
  {"id": "seja",    "subagents": {"allowAgents": ["hongmungwan"]}},
    {"id": "hongmungwan", "subagents": {"allowAgents": ["saganwon", "seungjeongwon"]}},
    {"id": "saganwon",   "subagents": {"allowAgents": ["seungjeongwon", "hongmungwan"]}},
  {"id": "seungjeongwon", "subagents": {"allowAgents": ["hongmungwan", "saganwon", "hojo", "yejo", "byeongjo", "hyeongjo", "gongjo", "ijo"]}},
    {"id": "hojo",     "subagents": {"allowAgents": ["seungjeongwon"]}},
    {"id": "yejo",     "subagents": {"allowAgents": ["seungjeongwon"]}},
    {"id": "byeongjo",   "subagents": {"allowAgents": ["seungjeongwon"]}},
    {"id": "hyeongjo",   "subagents": {"allowAgents": ["seungjeongwon"]}},
    {"id": "gongjo",   "subagents": {"allowAgents": ["seungjeongwon"]}},
  {"id": "ijo",  "subagents": {"allowAgents": ["seungjeongwon"]}},
  {"id": "jobocheong",  "subagents": {"allowAgents": []}},
]

agents_cfg = cfg.setdefault('agents', {})
agents_list = agents_cfg.get('list', [])
existing_ids = {a['id'] for a in agents_list}

added = 0
for ag in AGENTS:
    ag_id = ag['id']
    ws = str(oc_home / f'workspace-{ag_id}')
    if ag_id not in existing_ids:
        entry = {'id': ag_id, 'workspace': ws, **{k:v for k,v in ag.items() if k!='id'}}
        agents_list.append(entry)
        added += 1
        print(f'  + 추가됨: {ag_id}')
    else:
        print(f'  ~ 존재함: {ag_id} (건너뜀)')

agents_cfg['list'] = agents_list

# Fix #142: bindings에서 불법 필드 정리 (pattern은 gateway에서 지원하지 않음)
bindings = cfg.get('bindings', [])
cleaned = 0
for b in bindings:
    match = b.get('match', {})
    if isinstance(match, dict) and 'pattern' in match:
        del match['pattern']
        cleaned += 1
        print(f'  🧹 binding에서 불법 "pattern" 제거: {b.get("agentId", "?")}')
if cleaned:
    print(f'불법 binding 필드 {cleaned}개 정리됨')

cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
print(f'완료: {added}개 에이전트 추가됨')
PYEOF

  log "Agents 등록 완료"
}

# ── Step 3: 데이터 초기화 ─────────────────────────────────────
init_data() {
  info "데이터 디렉토리 초기화 중..."
  
  mkdir -p "$REPO_DIR/data"
  
  # 빈 파일 초기화
  for f in live_status.json agent_config.json model_change_log.json; do
    if [ ! -f "$REPO_DIR/data/$f" ]; then
      echo '{}' > "$REPO_DIR/data/$f"
    fi
  done
  echo '[]' > "$REPO_DIR/data/pending_model_changes.json"

  # 초기 작업 파일
  if [ ! -f "$REPO_DIR/data/tasks_source.json" ]; then
    python3 << 'PYEOF'
import json, pathlib
tasks = [
    {
        "id": "JJC-DEMO-001",
        "title": "🎉 시스템 초기화 완료",
        "official": "공조판서",
        "org": "공조",
        "state": "Completed",
        "now": "3사6조 시스템이 준비되었습니다",
        "eta": "-",
        "block": "없음",
        "output": "",
        "ac": "시스템 정상 작동",
        "flow_log": [
            {"at": "2024-01-01T00:00:00Z", "from": "임금", "to": "홍문관", "remark": "지침 하달: 3사6조 시스템 초기화"},
            {"at": "2024-01-01T00:01:00Z", "from": "홍문관", "to": "사간원", "remark": "기획안 심의 제출"},
            {"at": "2024-01-01T00:02:00Z", "from": "사간원", "to": "승정원", "remark": "✅ 주청"},
            {"at": "2024-01-01T00:03:00Z", "from": "승정원", "to": "공조", "remark": "파견: 시스템 초기화"},
            {"at": "2024-01-01T00:04:00Z", "from": "공조", "to": "승정원", "remark": "✅ 완료"},
        ]
    }
]
import os
data_dir = pathlib.Path(os.environ.get('REPO_DIR', '.')) / 'data'
data_dir.mkdir(exist_ok=True)
(data_dir / 'tasks_source.json').write_text(json.dumps(tasks, ensure_ascii=False, indent=2))
print('tasks_source.json 초기화됨')
PYEOF
  fi

  log "데이터 디렉토리 초기화 완료: $REPO_DIR/data"
}

# ── Step 3.3: 데이터 일관성을 위한 data/scripts 심볼릭 링크 생성 (Fix #88) ─────────
link_resources() {
  info "Agent 데이터 일관성을 위한 data/scripts 심볼릭 링크 생성 중..."
  
  AGENTS=(seja hongmungwan saganwon seungjeongwon hojo yejo byeongjo hyeongjo gongjo ijo jobocheong)
  LINKED=0
  for agent in "${AGENTS[@]}"; do
    ws="$OC_HOME/workspace-$agent"
    mkdir -p "$ws"

    # data 디렉토리 심볼릭 링크: 모든 agent가 동일한 tasks_source.json을 읽도록
    ws_data="$ws/data"
    if [ -L "$ws_data" ]; then
      : # 이미 심볼릭 링크임
    elif [ -d "$ws_data" ]; then
      # 기존 data 디렉토리(심볼릭 링크 아님) 백업 후 교체
      mv "$ws_data" "${ws_data}.bak.$(date +%Y%m%d-%H%M%S)"
      ln -s "$REPO_DIR/data" "$ws_data"
      LINKED=$((LINKED + 1))
    else
      ln -s "$REPO_DIR/data" "$ws_data"
      LINKED=$((LINKED + 1))
    fi

    # scripts 디렉토리 심볼릭 링크
    ws_scripts="$ws/scripts"
    if [ -L "$ws_scripts" ]; then
      : # 이미 심볼릭 링크임
    elif [ -d "$ws_scripts" ]; then
      mv "$ws_scripts" "${ws_scripts}.bak.$(date +%Y%m%d-%H%M%S)"
      ln -s "$REPO_DIR/scripts" "$ws_scripts"
      LINKED=$((LINKED + 1))
    else
      ln -s "$REPO_DIR/scripts" "$ws_scripts"
      LINKED=$((LINKED + 1))
    fi
  done

  # Legacy: workspace-main
  ws_main="$OC_HOME/workspace-main"
  if [ -d "$ws_main" ]; then
    for target in data scripts; do
      link_path="$ws_main/$target"
      if [ ! -L "$link_path" ]; then
        [ -d "$link_path" ] && mv "$link_path" "${link_path}.bak.$(date +%Y%m%d-%H%M%S)"
        ln -s "$REPO_DIR/$target" "$link_path"
        LINKED=$((LINKED + 1))
      fi
    done
  fi

  log "심볼릭 링크 $LINKED개 생성됨 (data/scripts → 프로젝트 디렉토리)"
}

# ── Step 3.5: Agent 간 통신 가시성 설정 (Fix #83) ──────────────
setup_visibility() {
  info "Agent 간 메시지 가시성 설정 중..."
  if openclaw config set tools.sessions.visibility all 2>/dev/null; then
    log "tools.sessions.visibility=all 설정됨 (Agent 간 통신 가능)"
  else
    warn "가시성 설정 실패 (openclaw 버전이 지원하지 않을 수 있음), 수동으로 실행하세요:"
    echo "    openclaw config set tools.sessions.visibility all"
  fi
}

# ── Step 3.5b: 모든 Agent에 API Key 동기화 ──────────────────────────
sync_auth() {
  info "모든 Agent에 API Key 동기화 중..."

  # OpenClaw ≥ 3.13은 models.json에 인증 정보 저장, 이전 버전은 auth-profiles.json 사용
  MAIN_AUTH=""
  AUTH_FILENAME=""
  AGENT_BASE="$OC_HOME/agents/main/agent"

  for candidate in models.json auth-profiles.json; do
    if [ -f "$AGENT_BASE/$candidate" ]; then
      MAIN_AUTH="$AGENT_BASE/$candidate"
      AUTH_FILENAME="$candidate"
      break
    fi
  done

  # Fallback: 모든 agent에서 파일명 검색
  if [ -z "$MAIN_AUTH" ]; then
    for candidate in models.json auth-profiles.json; do
      MAIN_AUTH=$(find "$OC_HOME/agents" -name "$candidate" -maxdepth 3 2>/dev/null | head -1)
      if [ -n "$MAIN_AUTH" ] && [ -f "$MAIN_AUTH" ]; then
        AUTH_FILENAME="$candidate"
        break
      fi
      MAIN_AUTH=""
    done
  fi

  if [ -z "$MAIN_AUTH" ] || [ ! -f "$MAIN_AUTH" ]; then
    warn "models.json 또는 auth-profiles.json을 찾을 수 없습니다"
    warn "먼저 임의의 Agent에 API Key를 설정하세요:"
    echo "    openclaw agents add seja"
    echo "  그 후 install.sh를 다시 실행하거나, 수동으로 실행하세요:"
    echo "    bash install.sh --sync-auth"
    return
  fi

  # 파일 내용이 유효한지 확인 (비어있지 않은 JSON)
  if ! python3 -c "import json; d=json.load(open('$MAIN_AUTH')); assert d" 2>/dev/null; then
    warn "$AUTH_FILENAME이 비어있거나 유효하지 않습니다. 먼저 API Key를 설정하세요:"
    echo "    openclaw agents add seja"
    return
  fi

  AGENTS=(seja hongmungwan saganwon seungjeongwon hojo yejo byeongjo hyeongjo gongjo ijo jobocheong)
  SYNCED=0
  for agent in "${AGENTS[@]}"; do
    AGENT_DIR="$OC_HOME/agents/$agent/agent"
    if [ -d "$AGENT_DIR" ] || mkdir -p "$AGENT_DIR" 2>/dev/null; then
      cp "$MAIN_AUTH" "$AGENT_DIR/$AUTH_FILENAME"
      SYNCED=$((SYNCED + 1))
    fi
  done

  log "API Key가 $SYNCED개 Agent에 동기화됨"
  info "출처: $MAIN_AUTH"
}

# ── Step 4: 프론트엔드 빌드 ──────────────────────────────────────────
build_frontend() {
  info "React 프론트엔드 빌드 중..."

  if ! command -v node &>/dev/null; then
    warn "node를 찾을 수 없습니다. 프론트엔드 빌드를 건너뜁니다. 미리 빌드된 버전이 사용됩니다 (있는 경우)"
    warn "Node.js 18+를 설치한 후 실행하세요: cd edict/frontend && npm install && npm run build"
    return
  fi

  if [ -f "$REPO_DIR/edict/frontend/package.json" ]; then
    cd "$REPO_DIR/edict/frontend"
    npm install --silent 2>/dev/null || npm install
    npm run build 2>/dev/null
    cd "$REPO_DIR"
    if [ -f "$REPO_DIR/dashboard/dist/index.html" ]; then
      log "프론트엔드 빌드 완료: dashboard/dist/"
    else
      warn "프론트엔드 빌드에 실패했을 수 있습니다. 수동으로 확인하세요"
    fi
  else
    warn "edict/frontend/package.json을 찾을 수 없습니다. 프론트엔드 빌드를 건너뜁니다"
  fi
}

# ── Step 5: 초기 데이터 동기화 ────────────────────────────────────
first_sync() {
  info "초기 데이터 동기화 실행 중..."
  cd "$REPO_DIR"
  
  REPO_DIR="$REPO_DIR" python3 scripts/sync_agent_config.py || warn "sync_agent_config 경고 있음"
  python3 scripts/sync_officials_stats.py || warn "sync_officials_stats 경고 있음"
  python3 scripts/refresh_live_data.py || warn "refresh_live_data 경고 있음"
  
  log "초기 동기화 완료"
}

# ── Step 6: Gateway 재시작 ────────────────────────────────────
restart_gateway() {
  info "OpenClaw Gateway 재시작 중..."
  if openclaw gateway restart 2>/dev/null; then
    log "Gateway 재시작 성공"
  else
    warn "Gateway 재시작 실패, 수동으로 재시작하세요: openclaw gateway restart"
  fi
}

# ── Main ────────────────────────────────────────────────────
banner
check_deps
backup_existing
create_workspaces
register_agents
init_data
link_resources
setup_visibility
sync_auth
build_frontend
first_sync
restart_gateway

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🎉  3사6조 설치 완료！                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "다음 단계:"
echo "  1. API Key 설정 (아직 설정하지 않은 경우):"
echo "     openclaw agents add seja     # 안내에 따라 Anthropic API Key 입력"
echo "     ./install.sh                  # 모든 Agent에 동기화하려면 다시 실행"
echo "  2. 데이터 새로고침 루프 시작:  bash scripts/run_loop.sh &"
echo "  3. 대시보드 서버 시작:    python3 \"\$REPO_DIR/dashboard/server.py\""
echo "  4. 대시보드 열기:          http://127.0.0.1:7891"
echo ""
warn "처음 설치 시 반드시 API Key를 설정해야 합니다. 그렇지 않으면 Agent가 오류를 보고합니다"
info "문서: docs/getting-started.md"
