"""Agents API — Agent 설정 및 상태 조회."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter

log = logging.getLogger("edict.api.agents")
router = APIRouter()

# Agent 메타정보 (agents/ 디렉토리 하위 SOUL.md에 대응)
AGENT_META = {
    "jobocheong": {"name": "조보청（조회 주관）", "role": "조회 소집 및 의안 관리", "icon": "🏛️"},
    "seungjeongwon": {"name": "승정원", "role": "총괄 조율 및 업무 감독", "icon": "📜"},
    "hongmungwan": {"name": "홍문관", "role": "조령 및 방안 기획", "icon": "✍️"},
    "saganwon": {"name": "사간원", "role": "심의 및 봉박", "icon": "🔍"},
    "yejo": {"name": "예조", "role": "문서/규범/UI/대외 소통", "icon": "📝"},
    "ijo": {"name": "이조", "role": "인사 및 Agent 관리/교육", "icon": "👔"},
    "hojo": {"name": "호조", "role": "재무 및 자원 관리", "icon": "💰"},
    "gongjo": {"name": "공조", "role": "공정 및 기술 실시", "icon": "🔧"},
    "hyeongjo": {"name": "형조", "role": "규범 및 품질 심사", "icon": "⚖️"},
    "byeongjo": {"name": "병조", "role": "안전 및 응급 대응", "icon": "🛡️"},
    "gwansanggam": {"name": "관상감", "role": "천문 및 역법 관리", "icon": "🔭"},
}


@router.get("")
async def list_agents():
    """모든 사용 가능한 Agent 목록."""
    agents = []
    for agent_id, meta in AGENT_META.items():
        agents.append({
            "id": agent_id,
            **meta,
        })
    return {"agents": agents}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Agent 상세 정보 조회."""
    meta = AGENT_META.get(agent_id)
    if not meta:
        return {"error": f"Agent '{agent_id}' not found"}, 404

    # SOUL.md 읽기 시도
    soul_path = Path(__file__).parents[4] / "agents" / agent_id / "SOUL.md"
    soul_content = ""
    if soul_path.exists():
        soul_content = soul_path.read_text(encoding="utf-8")[:2000]

    return {
        "id": agent_id,
        **meta,
        "soul_preview": soul_content,
    }


@router.get("/{agent_id}/config")
async def get_agent_config(agent_id: str):
    """Agent 실행 시 설정 조회."""
    config_path = Path(__file__).parents[4] / "data" / "agent_config.json"
    if not config_path.exists():
        return {"agent_id": agent_id, "config": {}}

    try:
        configs = json.loads(config_path.read_text(encoding="utf-8"))
        agent_config = configs.get(agent_id, {})
        return {"agent_id": agent_id, "config": agent_config}
    except (json.JSONDecodeError, IOError):
        return {"agent_id": agent_id, "config": {}}
