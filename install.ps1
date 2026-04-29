# ═══════════════════════════════════════════════════════════
# 3사6조 · OpenClaw Multi-Agent System 원클릭 설치 스크립트 (Windows)
# PowerShell 버전 — install.sh에 대응
# ═══════════════════════════════════════════════════════════
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$REPO_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$OC_HOME = if ($env:OPENCLAW_HOME) { $env:OPENCLAW_HOME } else { Join-Path $env:USERPROFILE ".openclaw" }
$OC_CFG = Join-Path $OC_HOME "openclaw.json"

function Write-Banner {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Blue
    Write-Host "║  🏛️  3사6조 · OpenClaw Multi-Agent     ║" -ForegroundColor Blue
    Write-Host "║       설치 마법사 (Windows)                  ║" -ForegroundColor Blue
    Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Blue
    Write-Host ""
}

function Log   { param($msg) Write-Host "✅ $msg" -ForegroundColor Green }
function Warn  { param($msg) Write-Host "⚠️  $msg" -ForegroundColor Yellow }
function Error { param($msg) Write-Host "❌ $msg" -ForegroundColor Red }
function Info  { param($msg) Write-Host "ℹ️  $msg" -ForegroundColor Blue }

# ── Step 0: 의존성 확인 ──
function Check-Deps {
    Info "의존성 확인 중..."

    $oc = Get-Command openclaw -ErrorAction SilentlyContinue
    if (-not $oc) {
        Error "openclaw CLI를 찾을 수 없습니다. 먼저 OpenClaw를 설치하세요: https://openclaw.ai"
        exit 1
    }
    Log "OpenClaw CLI: OK"

    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) {
        $py = Get-Command python3 -ErrorAction SilentlyContinue
    }
    if (-not $py) {
        Error "python3 또는 python을 찾을 수 없습니다"
        exit 1
    }
    $global:PYTHON = $py.Source
    Log "Python: $($global:PYTHON)"

    if (-not (Test-Path $OC_CFG)) {
        Error "openclaw.json을 찾을 수 없습니다. 먼저 openclaw를 실행하여 초기화하세요."
        exit 1
    }
    Log "openclaw.json: $OC_CFG"
}

# ── Step 0.5: 기존 Agent 데이터 백업 ──
function Backup-Existing {
    $hasExisting = Get-ChildItem -Path $OC_HOME -Directory -Filter "workspace-*" -ErrorAction SilentlyContinue
    if ($hasExisting) {
        Info "기존 Agent 워크스페이스 감지, 자동 백업 중..."
        $ts = Get-Date -Format "yyyyMMdd-HHmmss"
        $backupDir = Join-Path $OC_HOME "backups\pre-install-$ts"
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

        Get-ChildItem -Path $OC_HOME -Directory -Filter "workspace-*" | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination (Join-Path $backupDir $_.Name) -Recurse
        }

        if (Test-Path $OC_CFG) {
            Copy-Item $OC_CFG (Join-Path $backupDir "openclaw.json")
        }
        Log "백업 완료: $backupDir"
    }
}

# ── Step 1: 워크스페이스 생성 ──
function Create-Workspaces {
    Info "Agent 워크스페이스 생성 중..."

    $agents = @("seja","hongmungwan","saganwon","seungjeongwon","hojo","yejo","byeongjo","hyeongjo","gongjo","ijo","jobocheong")
    foreach ($agent in $agents) {
        $ws = Join-Path $OC_HOME "workspace-$agent"
        New-Item -ItemType Directory -Path (Join-Path $ws "skills") -Force | Out-Null

        $soulSrc = Join-Path $REPO_DIR "agents\$agent\SOUL.md"
        $soulDst = Join-Path $ws "SOUL.md"
        if (Test-Path $soulSrc) {
            if (Test-Path $soulDst) {
                $ts = Get-Date -Format "yyyyMMdd-HHmmss"
                Copy-Item $soulDst "$soulDst.bak.$ts"
                Warn "기존 SOUL.md 백업됨 → $soulDst.bak.$ts"
            }
            $content = (Get-Content $soulSrc -Raw) -replace "__REPO_DIR__", $REPO_DIR
            Set-Content -Path $soulDst -Value $content -Encoding UTF8
        }
        Log "워크스페이스 생성됨: $ws"

        # AGENTS.md
        $agentsMd = @"
# AGENTS.md · 작업 프로토콜

1. 임무를 받으면 "지침을 받았습니다"라고 먼저 회신합니다.
2. 출력에는 반드시 다음을 포함합니다: 임무 ID, 결과, 증거/파일 경로, 차단 항목.
3. 협업이 필요한 경우, 상서성을 통해 파견을 요청하며 부서 간 직접 연결하지 않습니다.
4. 삭제/외부 전송 작업은 명시적으로 표시하고 승인을 기다립니다.
"@
        Set-Content -Path (Join-Path $ws "AGENTS.md") -Value $agentsMd -Encoding UTF8
    }
}

# ── Step 2: Agent 등록 ──
function Register-Agents {
    Info "3사6조 Agents 등록 중..."

    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item $OC_CFG "$OC_CFG.bak.sansheng-$ts"
    Log "설정 백업됨: $OC_CFG.bak.*"

    $pyScript = @"
import json, pathlib, sys, os

oc_home = pathlib.Path(
    os.environ.get('OPENCLAW_HOME', str(pathlib.Path(os.environ['USERPROFILE']) / '.openclaw'))
).expanduser()
cfg_path = oc_home / 'openclaw.json'
cfg = json.loads(cfg_path.read_text(encoding='utf-8'))

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

# Fix #142: clean invalid binding pattern
bindings = cfg.get('bindings', [])
for b in bindings:
    match = b.get('match', {})
    if isinstance(match, dict) and 'pattern' in match:
        del match['pattern']
        print(f'  불법 pattern 제거됨: {b.get("agentId", "?")}')

cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'완료: {added}개 에이전트 추가됨')
"@
    & $global:PYTHON -c $pyScript
    Log "Agents 등록 완료"
}

# ── Step 3: 데이터 초기화 ──
function Init-Data {
    Info "데이터 디렉토리 초기화 중..."
    $dataDir = Join-Path $REPO_DIR "data"
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null

    foreach ($f in @("live_status.json","agent_config.json","model_change_log.json")) {
        $fp = Join-Path $dataDir $f
        if (-not (Test-Path $fp)) { Set-Content $fp "{}" -Encoding UTF8 }
    }
    Set-Content (Join-Path $dataDir "pending_model_changes.json") "[]" -Encoding UTF8
    Log "데이터 디렉토리 초기화 완료"
}

# ── Step 3.3: data/scripts 디렉토리 연결 생성 (Junction) ──
function Link-Resources {
    Info "data/scripts 디렉토리 연결 생성 중..."
    $linked = 0
    $agents = @("seja","hongmungwan","saganwon","seungjeongwon","hojo","yejo","byeongjo","hyeongjo","gongjo","ijo","jobocheong")
    foreach ($agent in $agents) {
        $ws = Join-Path $OC_HOME "workspace-$agent"
        New-Item -ItemType Directory -Path $ws -Force | Out-Null

        # data 디렉토리
        $wsData = Join-Path $ws "data"
        $srcData = Join-Path $REPO_DIR "data"
        if (-not (Test-Path $wsData)) {
            cmd /c mklink /J "$wsData" "$srcData" | Out-Null
            $linked++
        } elseif (-not ((Get-Item $wsData).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            $ts = Get-Date -Format "yyyyMMdd-HHmmss"
            Rename-Item $wsData "$wsData.bak.$ts"
            cmd /c mklink /J "$wsData" "$srcData" | Out-Null
            $linked++
        }

        # scripts 디렉토리
        $wsScripts = Join-Path $ws "scripts"
        $srcScripts = Join-Path $REPO_DIR "scripts"
        if (-not (Test-Path $wsScripts)) {
            cmd /c mklink /J "$wsScripts" "$srcScripts" | Out-Null
            $linked++
        } elseif (-not ((Get-Item $wsScripts).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            $ts = Get-Date -Format "yyyyMMdd-HHmmss"
            Rename-Item $wsScripts "$wsScripts.bak.$ts"
            cmd /c mklink /J "$wsScripts" "$srcScripts" | Out-Null
            $linked++
        }
    }
    Log "디렉토리 연결 $linked개 생성됨 (data/scripts → 프로젝트 디렉토리)"
}

# ── Step 3.5: Agent 간 통신 가시성 설정 ──
function Setup-Visibility {
    Info "Agent 간 메시지 가시성 설정 중..."
    try {
        openclaw config set tools.sessions.visibility all 2>$null
        Log "tools.sessions.visibility=all 설정됨"
    } catch {
        Warn "가시성 설정 실패, 수동으로 실행하세요: openclaw config set tools.sessions.visibility all"
    }
}

# ── Step 4: 프론트엔드 빌드 ──
function Build-Frontend {
    Info "React 프론트엔드 빌드 중..."
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        Warn "node를 찾을 수 없습니다. 프론트엔드 빌드를 건너뜁니다."
        Warn "Node.js 18+를 설치한 후 실행하세요: cd edict\frontend && npm install && npm run build"
        return
    }
    $pkgJson = Join-Path $REPO_DIR "edict\frontend\package.json"
    if (Test-Path $pkgJson) {
        Push-Location (Join-Path $REPO_DIR "edict\frontend")
        npm install --silent 2>$null
        npm run build 2>$null
        Pop-Location
        $indexHtml = Join-Path $REPO_DIR "dashboard\dist\index.html"
        if (Test-Path $indexHtml) {
            Log "프론트엔드 빌드 완료: dashboard\dist\"
        } else {
            Warn "프론트엔드 빌드에 실패했을 수 있습니다. 수동으로 확인하세요"
        }
    }
}

# ── Step 5: 초기 데이터 동기화 ──
function First-Sync {
    Info "초기 데이터 동기화 실행 중..."
    Push-Location $REPO_DIR
    $env:REPO_DIR = $REPO_DIR
    try { & $global:PYTHON scripts/sync_agent_config.py } catch { Warn "sync_agent_config 경고 있음" }
    try { & $global:PYTHON scripts/sync_officials_stats.py } catch { Warn "sync_officials_stats 경고 있음" }
    try { & $global:PYTHON scripts/refresh_live_data.py } catch { Warn "refresh_live_data 경고 있음" }
    Pop-Location
    Log "초기 동기화 완료"
}

# ── Step 6: Gateway 재시작 ──
function Restart-Gateway {
    Info "OpenClaw Gateway 재시작 중..."
    try {
        openclaw gateway restart 2>$null
        Log "Gateway 재시작 성공"
    } catch {
        Warn "Gateway 재시작 실패, 수동으로 재시작하세요: openclaw gateway restart"
    }
}

# ── Main ──
Write-Banner
Check-Deps
Backup-Existing
Create-Workspaces
Register-Agents
Init-Data
Link-Resources
Setup-Visibility
Build-Frontend
First-Sync
Restart-Gateway

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  🎉  3사6조 설치 완료！                          ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "다음 단계:"
Write-Host "  1. API Key 설정 (아직 설정하지 않은 경우):"
Write-Host "     openclaw agents add seja     # 안내에 따라 Anthropic API Key 입력"
Write-Host "     .\install.ps1                 # 모든 Agent에 동기화하려면 다시 실행"
Write-Host "  2. 데이터 새로고침 루프 시작:  bash scripts/run_loop.sh"
Write-Host "  3. 대시보드 서버 시작:    python dashboard/server.py"
Write-Host "  4. 대시보드 열기:          http://127.0.0.1:7891"
Write-Host ""
Warn "처음 설치 시 반드시 API Key를 설정해야 합니다. 그렇지 않으면 Agent가 오류를 보고합니다"
Info "문서: docs/getting-started.md"
