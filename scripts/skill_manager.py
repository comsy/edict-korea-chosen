#!/usr/bin/env python3
"""
조선식 Skill 관리 도구
로컬 또는 원격 URL에서 skill 을 추가, 갱신, 조회, 제거할 수 있습니다.

Usage:
  python3 scripts/skill_manager.py add-remote --agent zhongshu --name code_review \\
    --source https://raw.githubusercontent.com/org/skills/main/code_review/SKILL.md \\
    --description "코드 리뷰"

  python3 scripts/skill_manager.py list-remote

  python3 scripts/skill_manager.py update-remote --agent zhongshu --name code_review

  python3 scripts/skill_manager.py remove-remote --agent zhongshu --name code_review

  python3 scripts/skill_manager.py import-official-hub --agents zhongshu,menxia,shangshu
"""
import sys
import json
import pathlib
import argparse
import os
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import get_openclaw_home, now_iso, safe_name, read_json

OCLAW_HOME = get_openclaw_home()


def _download_file(url: str, timeout: int = 30, retries: int = 3) -> str:
    """URL 에서 텍스트 파일을 내려받는다. 실패 시 재시도한다."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'OpenClaw-SkillManager/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read(10 * 1024 * 1024)  # 最多 10MB
                return content.decode('utf-8')
        except urllib.error.HTTPError as e:
            last_error = f'HTTP {e.code}: {e.reason}'
            if e.code in (404, 403):
                break  # 不重试 4xx
        except urllib.error.URLError as e:
            last_error = f'网络错误: {e.reason}'
        except Exception as e:
            last_error = f'{type(e).__name__}: {e}'
        
        if attempt < retries:
            import time
            wait = attempt * 3  # 3s, 6s
            print(f'   ⚠️ {attempt}번째 다운로드에 실패했습니다 ({last_error}). {wait}초 후 다시 시도합니다...')
            time.sleep(wait)
    
    # 所有重试失败
    hint = ''
    if 'timed out' in str(last_error).lower() or '超时' in str(last_error):
        hint = '\n   💡 안내: 네트워크 제약이 있으면 https_proxy 환경 변수를 설정해 주세요'
    elif '404' in str(last_error):
        hint = '\n   💡 안내: 공식 Skills Hub 에 아직 없는 skill 일 수 있으니 URL 을 다시 확인해 주세요'
    raise Exception(f'{last_error} (총 {retries}회 재시도){hint}')


def _compute_checksum(content: str) -> str:
    """내용 검증용 간단한 체크섬을 계산한다."""
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def add_remote(agent_id: str, name: str, source_url: str, description: str = '') -> bool:
    """원격 URL 에서 Agent 용 skill 을 추가한다."""
    if not safe_name(agent_id) or not safe_name(name):
        print('❌ 오류: agent_id 또는 skill 이름에 허용되지 않은 문자가 있습니다')
        return False
    
    # 设置 workspace
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / name
    workspace.mkdir(parents=True, exist_ok=True)
    skill_md = workspace / 'SKILL.md'
    
    # 下载文件
    print(f'⏳ {source_url} 에서 내려받는 중...')
    try:
        content = _download_file(source_url)
    except Exception as e:
        print(f'❌ 다운로드 실패: {e}')
        print(f'   URL: {source_url}')
        return False
    
    # 基础验证（放宽检查：有些 skill 不以 --- 开头）
    if len(content.strip()) < 10:
        print('❌ 파일 내용이 비어 있거나 너무 짧습니다')
        return False
    
    # 保存 SKILL.md
    skill_md.write_text(content)
    
    # 保存源信息
    source_info = {
        'skillName': name,
        'sourceUrl': source_url,
        'description': description,
        'addedAt': now_iso(),
        'lastUpdated': now_iso(),
        'checksum': _compute_checksum(content),
        'status': 'valid',
    }
    source_json = workspace / '.source.json'
    source_json.write_text(json.dumps(source_info, ensure_ascii=False, indent=2))
    
    print(f'✅ skill {name} 을(를) {agent_id} 에 추가했습니다')
    print(f'   경로: {skill_md}')
    print(f'   크기: {len(content)} 바이트')
    return True


def list_remote() -> bool:
    """추가된 원격 skill 목록을 출력한다."""
    if not OCLAW_HOME.exists():
        print('❌ OCLAW_HOME 경로가 존재하지 않습니다')
        return False
    
    remote_skills = []
    
    for ws_dir in OCLAW_HOME.glob('workspace-*'):
        agent_id = ws_dir.name.replace('workspace-', '')
        skills_dir = ws_dir / 'skills'
        if not skills_dir.exists():
            continue
        
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            source_json = skill_dir / '.source.json'
            
            if not source_json.exists():
                continue
            
            try:
                source_info = json.loads(source_json.read_text())
                remote_skills.append({
                    'agent': agent_id,
                    'skill': skill_name,
                    'source': source_info.get('sourceUrl', 'N/A'),
                    'desc': source_info.get('description', ''),
                    'added': source_info.get('addedAt', 'N/A'),
                })
            except Exception:
                pass
    
    if not remote_skills:
        print('📭 등록된 원격 skill 이 없습니다')
        return True
    
    print(f'📋 원격 skill 총 {len(remote_skills)}개\n')
    print(f'{"Agent":<12} | {"Skill 이름":<20} | {"설명":<30} | 추가일')
    print('-' * 100)
    
    for sk in remote_skills:
        desc = (sk['desc'] or sk['source'])[:30].ljust(30)
        print(f"{sk['agent']:<12} | {sk['skill']:<20} | {desc} | {sk['added'][:10]}")
    
    print()
    return True


def update_remote(agent_id: str, name: str) -> bool:
    """원격 skill 을 최신 버전으로 갱신한다."""
    if not safe_name(agent_id) or not safe_name(name):
        print('❌ 오류: agent_id 또는 skill 이름에 허용되지 않은 문자가 있습니다')
        return False
    
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / name
    source_json = workspace / '.source.json'
    
    if not source_json.exists():
        print(f'❌ 원격 skill 을 찾을 수 없습니다: {name}')
        return False
    
    try:
        source_info = json.loads(source_json.read_text())
        source_url = source_info.get('sourceUrl')
        if not source_url:
            print('❌ 원본 URL 이 비어 있거나 올바르지 않습니다')
            return False
        
        # 重新下载
        return add_remote(agent_id, name, source_url, source_info.get('description', ''))
    except Exception as e:
        print(f'❌ 갱신 실패: {e}')
        return False


def remove_remote(agent_id: str, name: str) -> bool:
    """원격 skill 을 제거한다."""
    if not safe_name(agent_id) or not safe_name(name):
        print('❌ 오류: agent_id 또는 skill 이름에 허용되지 않은 문자가 있습니다')
        return False
    
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / name
    source_json = workspace / '.source.json'
    
    if not source_json.exists():
        print(f'❌ 원격 skill 을 찾을 수 없습니다: {name}')
        return False
    
    try:
        import shutil
        shutil.rmtree(workspace)
        print(f'✅ skill {name} 을(를) {agent_id} 에서 제거했습니다')
        return True
    except Exception as e:
        print(f'❌ 제거 실패: {e}')
        return False


OFFICIAL_SKILLS_HUB_BASE = 'https://raw.githubusercontent.com/openclaw-ai/skills-hub/main'
# 보조 미러. 기본 URL 실패 시 자동으로 전환한다.
_FALLBACK_HUB_BASES = [
    'https://ghproxy.com/https://raw.githubusercontent.com/openclaw-ai/skills-hub/main',
    'https://raw.gitmirror.com/openclaw-ai/skills-hub/main',
]

# 환경 변수로 Skills Hub 주소를 덮어쓸 수 있다.
_HUB_BASE_ENV = 'OPENCLAW_SKILLS_HUB_BASE'

def _get_hub_url(skill_name):
    """skill 의 Hub URL 을 구한다. 환경 변수 override 를 지원한다."""
    hub_url_file = OCLAW_HOME / 'skills-hub-url'
    base = hub_url_file.read_text().strip() if hub_url_file.exists() else None
    base = base or os.environ.get(_HUB_BASE_ENV) or OFFICIAL_SKILLS_HUB_BASE
    return f'{base.rstrip("/")}/{skill_name}/SKILL.md'


OFFICIAL_SKILLS_HUB = {
    'code_review': _get_hub_url('code_review'),
    'api_design': _get_hub_url('api_design'),
    'security_audit': _get_hub_url('security_audit'),
    'data_analysis': _get_hub_url('data_analysis'),
    'doc_generation': _get_hub_url('doc_generation'),
    'test_framework': _get_hub_url('test_framework'),
    'mmx_cli': 'https://raw.githubusercontent.com/MiniMax-AI/cli/main/skill/SKILL.md',
}

SKILL_AGENT_MAPPING = {
    'code_review': ('bingbu', 'xingbu', 'menxia'),
    'api_design': ('bingbu', 'gongbu', 'menxia'),
    'security_audit': ('xingbu', 'menxia'),
    'data_analysis': ('hubu', 'menxia'),
    'doc_generation': ('libu', 'menxia'),
    'test_framework': ('gongbu', 'xingbu', 'menxia'),
    'mmx_cli': ('menxia', 'shangshu'),
}


def import_official_hub(agent_ids: list) -> bool:
    """공식 Skills Hub 에서 skill 을 가져와 지정한 agent 에 설치한다.
    agent 를 지정하지 않으면 skill 별 추천 agent 목록을 사용한다.
    """
    if not agent_ids:
        print('ℹ️ agent 를 따로 지정하지 않아 추천 구성을 사용합니다.\n')
        for skill_name, recommended_agents in SKILL_AGENT_MAPPING.items():
            agent_ids.extend(recommended_agents)
        agent_ids = list(set(agent_ids))
    
    total = 0
    success = 0
    failed = []
    
    for skill_name, url in OFFICIAL_SKILLS_HUB.items():
        # 确定目标 agents
        target_agents = agent_ids
        if not agent_ids:
            target_agents = SKILL_AGENT_MAPPING.get(skill_name, ['menxia'])
        
        print(f'\n📥 skill 가져오는 중: {skill_name}')
        print(f'   대상 agent: {", ".join(target_agents)}')
        
        # 尝试主 URL，失败则自动切换镜像
        effective_url = url
        for agent_id in target_agents:
            total += 1
            ok = add_remote(agent_id, skill_name, effective_url, f'공식 skill: {skill_name}')
            if not ok and effective_url == url:
                # 기본 URL 이 실패하면 미러를 시도한다.
                for fb_base in _FALLBACK_HUB_BASES:
                    fb_url = f'{fb_base.rstrip("/")}/{skill_name}/SKILL.md'
                    print(f'   🔄 미러 시도: {fb_url}')
                    ok = add_remote(agent_id, skill_name, fb_url, f'공식 skill: {skill_name}')
                    if ok:
                        effective_url = fb_url
                        break
            if ok:
                success += 1
            else:
                failed.append(f'{agent_id}/{skill_name}')
    
    print(f'\n📊 가져오기 완료: {success}/{total}개 skill 성공')
    if failed:
        print('\n❌ 실패 목록:')
        for f in failed:
            print(f'   - {f}')
        print('\n💡 점검 가이드:')
        print(f'   1. 네트워크 확인: curl -I {OFFICIAL_SKILLS_HUB_BASE}/code_review/SKILL.md')
        print('   2. 프록시 설정: export https_proxy=http://your-proxy:port')
        print(f'   3. 미러 사용: export {_HUB_BASE_ENV}=https://ghproxy.com/{OFFICIAL_SKILLS_HUB_BASE}')
        print(f'   4. 사용자 정의 소스: echo "https://your-mirror/skills" > {OCLAW_HOME / "skills-hub-url"}')
        print('   5. 단일 재시도: python3 scripts/skill_manager.py add-remote --agent <agent> --name <skill> --source <url>')
    return success == total


def main():
    parser = argparse.ArgumentParser(description='조선식 Skill 관리 도구',
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest='cmd', help='명령')
    
    # add-remote
    add_parser = subparsers.add_parser('add-remote', help='원격 skill 추가')
    add_parser.add_argument('--agent', required=True, help='대상 Agent ID')
    add_parser.add_argument('--name', required=True, help='skill 내부 이름')
    add_parser.add_argument('--source', required=True, help='원격 URL 또는 로컬 경로')
    add_parser.add_argument('--description', default='', help='skill 설명')
    
    # list-remote
    subparsers.add_parser('list-remote', help='원격 skill 목록 보기')
    
    # update-remote
    update_parser = subparsers.add_parser('update-remote', help='원격 skill 갱신')
    update_parser.add_argument('--agent', required=True, help='Agent ID')
    update_parser.add_argument('--name', required=True, help='skill 이름')
    
    # remove-remote
    remove_parser = subparsers.add_parser('remove-remote', help='원격 skill 제거')
    remove_parser.add_argument('--agent', required=True, help='Agent ID')
    remove_parser.add_argument('--name', required=True, help='skill 이름')
    
    # import-official-hub
    import_parser = subparsers.add_parser('import-official-hub', help='공식 허브에서 skill 가져오기')
    import_parser.add_argument('--agents', default='', help='쉼표로 구분한 Agent ID 목록 (선택)')
    
    # check-updates
    check_parser = subparsers.add_parser('check-updates', help='업데이트 확인 (향후 기능)')
    check_parser.add_argument('--interval', default='weekly', 
                             help='확인 주기 (weekly/daily/monthly)')
    
    args = parser.parse_args()
    
    if not args.cmd:
        parser.print_help()
        return
    
    if args.cmd == 'add-remote':
        success = add_remote(args.agent, args.name, args.source, args.description)
        sys.exit(0 if success else 1)
    
    elif args.cmd == 'list-remote':
        success = list_remote()
        sys.exit(0 if success else 1)
    
    elif args.cmd == 'update-remote':
        success = update_remote(args.agent, args.name)
        sys.exit(0 if success else 1)
    
    elif args.cmd == 'remove-remote':
        success = remove_remote(args.agent, args.name)
        sys.exit(0 if success else 1)
    
    elif args.cmd == 'import-official-hub':
        agent_list = [a.strip() for a in args.agents.split(',') if a.strip()] if args.agents else []
        success = import_official_hub(agent_list)
        sys.exit(0 if success else 1)
    
    elif args.cmd == 'check-updates':
        print(f'⏳ 업데이트 확인 기능은 아직 구현되지 않았습니다 (주기: {args.interval})')
        print('   추후 지원 예정입니다.')


if __name__ == '__main__':
    main()
