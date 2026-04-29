#!/usr/bin/env python3
"""
同步 openclaw.json 中的 agent 配置 → data/agent_config.json
支持自动发现 agent workspace 下的 Skills 目录
"""
import json, os, pathlib, datetime, logging
from file_lock import atomic_json_write
from utils import get_openclaw_home

log = logging.getLogger('sync_agent_config')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

# Auto-detect project root (parent of scripts/)
BASE = pathlib.Path(__file__).parent.parent
DATA = BASE / 'data'
OPENCLAW_HOME = get_openclaw_home()
OPENCLAW_CFG = OPENCLAW_HOME / 'openclaw.json'

ID_LABEL = {
    'seja':        {'label': '세자',   'role': '세자',     'duty': '메시지 분류 및 회신',      'emoji': '🤴'},
    'main':        {'label': '세자',   'role': '세자',     'duty': '메시지 분류 및 회신',      'emoji': '🤴'},  # 구버전 호환
    'hongmungwan': {'label': '홍문관', 'role': '대제학',   'duty': '임무서 기초 및 우선순위',  'emoji': '📜'},
    'saganwon':    {'label': '사간원', 'role': '대사간',   'duty': '심의 및 반려 절차',        'emoji': '🔍'},
    'seungjeongwon': {'label': '승정원', 'role': '도승지', 'duty': '배분 및 승급 재결',        'emoji': '📮'},
    'yejo':        {'label': '예조',   'role': '예조판서', 'duty': '문서/보고/규범',           'emoji': '📝'},
    'hojo':        {'label': '호조',   'role': '호조판서', 'duty': '자원/예산/비용',           'emoji': '💰'},
    'byeongjo':    {'label': '병조',   'role': '병조판서', 'duty': '구현/아키텍처 설계',       'emoji': '⚔️'},
    'hyeongjo':    {'label': '형조',   'role': '형조판서', 'duty': '감사/컴플라이언스/레드라인','emoji': '⚖️'},
    'gongjo':      {'label': '공조',   'role': '공조판서', 'duty': '인프라/배포/운영',         'emoji': '🔧'},
    'ijo':         {'label': '이조',   'role': '이조판서', 'duty': '인사/교육/Agent 관리',     'emoji': '👔'},
    'jobocheong':  {'label': '조보청', 'role': '조보관',   'duty': '일일 뉴스 수집 및 보고',   'emoji': '📰'},
    'gwansanggam': {'label': '관상감', 'role': '관상감정', 'duty': '천문/역법/데이터 관측',    'emoji': '🔭'},
}

KNOWN_MODELS = [
    {'id': 'anthropic/claude-sonnet-4-6', 'label': 'Claude Sonnet 4.6', 'provider': 'Anthropic'},
    {'id': 'anthropic/claude-opus-4-5',   'label': 'Claude Opus 4.5',   'provider': 'Anthropic'},
    {'id': 'anthropic/claude-haiku-3-5',  'label': 'Claude Haiku 3.5',  'provider': 'Anthropic'},
    {'id': 'openai/gpt-4o',               'label': 'GPT-4o',            'provider': 'OpenAI'},
    {'id': 'openai/gpt-4o-mini',          'label': 'GPT-4o Mini',       'provider': 'OpenAI'},
    {'id': 'openai-codex/gpt-5.3-codex',  'label': 'GPT-5.3 Codex',    'provider': 'OpenAI Codex'},
    {'id': 'google/gemini-2.0-flash',     'label': 'Gemini 2.0 Flash',  'provider': 'Google'},
    {'id': 'google/gemini-2.5-pro',       'label': 'Gemini 2.5 Pro',    'provider': 'Google'},
    {'id': 'copilot/claude-sonnet-4',     'label': 'Claude Sonnet 4',   'provider': 'Copilot'},
    {'id': 'copilot/claude-opus-4.5',     'label': 'Claude Opus 4.5',   'provider': 'Copilot'},
    {'id': 'github-copilot/claude-opus-4.6', 'label': 'Claude Opus 4.6', 'provider': 'GitHub Copilot'},
    {'id': 'copilot/gpt-4o',              'label': 'GPT-4o',            'provider': 'Copilot'},
    {'id': 'copilot/gemini-2.5-pro',      'label': 'Gemini 2.5 Pro',    'provider': 'Copilot'},
    {'id': 'copilot/o3-mini',             'label': 'o3-mini',           'provider': 'Copilot'},
]


def normalize_model(model_value, fallback='unknown'):
    if isinstance(model_value, str) and model_value:
        return model_value
    if isinstance(model_value, dict):
        return model_value.get('primary') or model_value.get('id') or fallback
    return fallback


def get_skills(workspace: str):
    skills_dir = pathlib.Path(workspace) / 'skills'
    skills = []
    try:
        if skills_dir.exists():
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir():
                    md = d / 'SKILL.md'
                    desc = ''
                    if md.exists():
                        try:
                            for line in md.read_text(encoding='utf-8', errors='ignore').splitlines():
                                line = line.strip()
                                if line and not line.startswith('#') and not line.startswith('---'):
                                    desc = line[:100]
                                    break
                        except Exception:
                            desc = '(读取失败)'
                    skills.append({'name': d.name, 'path': str(md), 'exists': md.exists(), 'description': desc})
    except PermissionError as e:
        log.warning(f'Skills 目录访问受限: {e}')
    return skills


def _collect_openclaw_models(cfg):
    """从 openclaw.json 中收集所有已配置的 model id，与 KNOWN_MODELS 合并去重。
    解决 #127: 自定义 provider 的 model 不在下拉列表中。
    """
    known_ids = {m['id'] for m in KNOWN_MODELS}
    extra = []
    agents_cfg = cfg.get('agents', {})
    # 收集 defaults.model
    dm = normalize_model(agents_cfg.get('defaults', {}).get('model', {}), '')
    if dm and dm not in known_ids:
        extra.append({'id': dm, 'label': dm, 'provider': 'OpenClaw'})
        known_ids.add(dm)
    # 收集 defaults.models 中的所有模型（OpenClaw 默认启用的模型列表）
    defaults_models = agents_cfg.get('defaults', {}).get('models', {})
    if isinstance(defaults_models, dict):
        for model_id in defaults_models.keys():
            if model_id and model_id not in known_ids:
                provider = 'OpenClaw'
                if '/' in model_id:
                    provider = model_id.split('/')[0]
                extra.append({'id': model_id, 'label': model_id, 'provider': provider})
                known_ids.add(model_id)
    # 收集每个 agent 的 model
    for ag in agents_cfg.get('list', []):
        m = normalize_model(ag.get('model', ''), '')
        if m and m not in known_ids:
            extra.append({'id': m, 'label': m, 'provider': 'OpenClaw'})
            known_ids.add(m)
    # 收集 providers 中的 model id（如 copilot-proxy、anthropic 等）
    for pname, pcfg in cfg.get('providers', {}).items():
        for mid in (pcfg.get('models') or []):
            mid_str = mid if isinstance(mid, str) else (mid.get('id') or mid.get('name') or '')
            if mid_str and mid_str not in known_ids:
                extra.append({'id': mid_str, 'label': mid_str, 'provider': pname})
                known_ids.add(mid_str)
    return KNOWN_MODELS + extra


def main():
    cfg = {}
    try:
        cfg = json.loads(OPENCLAW_CFG.read_text(encoding='utf-8'))
    except Exception as e:
        log.warning(f'cannot read openclaw.json: {e}')
        return

    agents_cfg = cfg.get('agents', {})
    default_model = normalize_model(agents_cfg.get('defaults', {}).get('model', {}), 'unknown')
    agents_list = agents_cfg.get('list', [])
    merged_models = _collect_openclaw_models(cfg)

    result = []
    seen_ids = set()
    for ag in agents_list:
        ag_id = ag.get('id', '')
        if ag_id not in ID_LABEL:
            continue
        meta = ID_LABEL[ag_id]
        workspace = ag.get('workspace', str(OPENCLAW_HOME / f'workspace-{ag_id}'))
        if 'allowAgents' in ag:
            allow_agents = ag.get('allowAgents', []) or []
        else:
            allow_agents = ag.get('subagents', {}).get('allowAgents', [])
        result.append({
            'id': ag_id,
            'label': meta['label'], 'role': meta['role'], 'duty': meta['duty'], 'emoji': meta['emoji'],
            'model': normalize_model(ag.get('model', default_model), default_model),
            'defaultModel': default_model,
            'workspace': workspace,
            'skills': get_skills(workspace),
            'allowAgents': allow_agents,
        })
        seen_ids.add(ag_id)

    # 补充不在 openclaw.json agents list 中的 agent（仅保留已有 workspace）
    EXTRA_AGENTS = {
        'seja':   {'model': default_model, 'workspace': str(OPENCLAW_HOME / 'workspace-seja'),
                    'allowAgents': ['hongmungwan']},
        'main':    {'model': default_model, 'workspace': str(OPENCLAW_HOME / 'workspace-main'),
                    'allowAgents': ['hongmungwan','saganwon','seungjeongwon','hojo','yejo','byeongjo','hyeongjo','gongjo','ijo']},
        'jobocheong': {'model': default_model, 'workspace': str(OPENCLAW_HOME / 'workspace-jobocheong'),
                    'allowAgents': []},
        'ijo': {'model': default_model, 'workspace': str(OPENCLAW_HOME / 'workspace-ijo'),
                    'allowAgents': ['seungjeongwon']},
    }
    for ag_id, extra in EXTRA_AGENTS.items():
        if ag_id in seen_ids or ag_id not in ID_LABEL:
            continue
        extra_workspace = pathlib.Path(extra['workspace'])
        if not extra_workspace.exists():
            continue
        meta = ID_LABEL[ag_id]
        result.append({
            'id': ag_id,
            'label': meta['label'], 'role': meta['role'], 'duty': meta['duty'], 'emoji': meta['emoji'],
            'model': extra['model'],
            'defaultModel': default_model,
            'workspace': str(extra_workspace),
            'skills': get_skills(str(extra_workspace)),
            'allowAgents': extra['allowAgents'],
            'isDefaultModel': True,
        })

    # 保留已有的 dispatchChannel 配置 (Fix #139)
    existing_cfg = {}
    cfg_path = DATA / 'agent_config.json'
    if cfg_path.exists():
        try:
            existing_cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    payload = {
        'generatedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'defaultModel': default_model,
        'knownModels': merged_models,
        'dispatchChannel': existing_cfg.get('dispatchChannel') or os.getenv('DEFAULT_DISPATCH_CHANNEL', ''),
        'agents': result,
    }
    DATA.mkdir(exist_ok=True)
    atomic_json_write(DATA / 'agent_config.json', payload)
    log.info(f'{len(result)} agents synced')

    # 自动部署 SOUL.md 到 workspace（如果项目里有更新）
    deploy_soul_files(result)
    # 同步 scripts/ 到各 workspace（保持 kanban_update.py 等最新）
    sync_scripts_to_workspaces(result)


# 项目 agents/ 目录名 → 运行时 agent_id 映射
_SOUL_DEPLOY_MAP = {
    'seja': 'seja',
    'hongmungwan': 'hongmungwan',
    'saganwon': 'saganwon',
    'seungjeongwon': 'seungjeongwon',
    'yejo': 'yejo',
    'hojo': 'hojo',
    'byeongjo': 'byeongjo',
    'hyeongjo': 'hyeongjo',
    'gongjo': 'gongjo',
    'ijo': 'ijo',
    'jobocheong': 'jobocheong',
}

def _sync_script_symlink(src_file: pathlib.Path, dst_file: pathlib.Path) -> bool:
    """Create a symlink dst_file → src_file (resolved).

    Using symlinks instead of physical copies ensures that ``__file__`` in
    each script always resolves back to the project ``scripts/`` directory,
    so relative-path computations like ``Path(__file__).resolve().parent.parent``
    point to the correct project root regardless of which workspace runs the
    script.  (Fixes #56 — kanban data-path split)

    Returns True if the link was (re-)created, False if already up-to-date.
    """
    src_resolved = src_file.resolve()
    # Guard: skip if dst resolves to the same real path as src.
    # This happens when ws_scripts is itself a directory-level symlink pointing
    # to the project scripts/ dir (created by install.sh link_resources).
    # Without this check the function would unlink the real source file and
    # then create a self-referential symlink (foo.py -> foo.py).
    try:
        dst_resolved = dst_file.resolve()
    except OSError:
        dst_resolved = None
    if dst_resolved == src_resolved:
        return False
    # Already a correct symlink?
    if dst_file.is_symlink() and dst_resolved == src_resolved:
        return False
    # Remove stale file / old physical copy / broken symlink
    if dst_file.exists() or dst_file.is_symlink():
        dst_file.unlink()
    os.symlink(src_resolved, dst_file)
    return True


def _iter_runtime_targets(agent_rows: list[dict]) -> list[tuple[str, pathlib.Path]]:
    targets: list[tuple[str, pathlib.Path]] = []
    seen: set[tuple[str, pathlib.Path]] = set()
    for row in agent_rows:
        runtime_id = row.get('id')
        workspace = row.get('workspace')
        if not runtime_id or not workspace:
            continue
        ws_path = pathlib.Path(workspace)
        key = (runtime_id, ws_path)
        if key in seen:
            continue
        seen.add(key)
        targets.append(key)
    return targets


def sync_scripts_to_workspaces(agent_rows: list[dict]):
    """将项目 scripts/ 目录同步到各 agent workspace（保持 kanban_update.py 等最新）

    Uses symlinks so that ``__file__`` in workspace copies resolves to the
    project ``scripts/`` directory, keeping path-derived constants like
    ``TASKS_FILE`` pointing to the canonical ``data/`` folder.
    """
    scripts_src = BASE / 'scripts'
    if not scripts_src.is_dir():
        return
    synced = 0
    for runtime_id, workspace in _iter_runtime_targets(agent_rows):
        ws_scripts = workspace / 'scripts'
        ws_scripts.mkdir(parents=True, exist_ok=True)
        for src_file in scripts_src.iterdir():
            if src_file.suffix not in ('.py', '.sh') or src_file.stem.startswith('__'):
                continue
            dst_file = ws_scripts / src_file.name
            try:
                if _sync_script_symlink(src_file, dst_file):
                    synced += 1
            except Exception:
                continue
    if synced:
        log.info(f'{synced} script symlinks synced to workspaces')


def deploy_soul_files(agent_rows: list[dict]):
    """将项目 agents/xxx/SOUL.md 部署到 openclaw.json 에 정의된 workspace."""
    agents_dir = BASE / 'agents'
    runtime_to_project = {runtime_id: proj_name for proj_name, runtime_id in _SOUL_DEPLOY_MAP.items()}
    deployed = 0
    for runtime_id, workspace in _iter_runtime_targets(agent_rows):
        proj_name = runtime_to_project.get(runtime_id, 'seja' if runtime_id == 'main' else None)
        if proj_name is None:
            continue
        src = agents_dir / proj_name / 'SOUL.md'
        if not src.exists():
            continue
        ws_dst = workspace / 'SOUL.md'
        ws_dst.parent.mkdir(parents=True, exist_ok=True)
        # 只在内容不同时更新（避免不必要的写入）
        src_text = src.read_text(encoding='utf-8', errors='ignore')
        try:
            dst_text = ws_dst.read_text(encoding='utf-8', errors='ignore')
        except FileNotFoundError:
            dst_text = ''
        if src_text != dst_text:
            ws_dst.write_text(src_text, encoding='utf-8')
            deployed += 1
        runtime_root = workspace.parent
        # 세자兼容：같은 runtime root 아래 legacy main 디렉터리가 있으면 함께 동기화
        if runtime_id == 'seja':
            ag_dst = runtime_root / 'agents' / 'main' / 'SOUL.md'
            if ag_dst.parent.exists():
                ag_dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    ag_text = ag_dst.read_text(encoding='utf-8', errors='ignore')
                except FileNotFoundError:
                    ag_text = ''
                if src_text != ag_text:
                    ag_dst.write_text(src_text, encoding='utf-8')
        # workspace 와 같은 runtime root 아래 sessions 디렉터리 보장
        sess_dir = runtime_root / 'agents' / runtime_id / 'sessions'
        sess_dir.mkdir(parents=True, exist_ok=True)
    if deployed:
        log.info(f'{deployed} SOUL.md files deployed')


if __name__ == '__main__':
    main()
