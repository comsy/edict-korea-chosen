#!/usr/bin/env python3
"""JSON → Postgres 데이터 마이그레이션 스크립트.

구버전 data/tasks_source.json을 읽어 Edict Postgres 데이터베이스로 가져옵니다.

사용법:
  # Postgres 실행 중이고 schema가 생성된 상태 확인 (alembic upgrade head)
  python3 migrate_json_to_pg.py

  # 데이터 파일 직접 지정
  python3 migrate_json_to_pg.py --file /path/to/tasks_source.json

  # 시험 실행 (분석만, 기록 안 함)
  python3 migrate_json_to_pg.py --dry-run
"""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# 添加 backend 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import text
from app.db import engine, async_session, Base
from app.models.task import Task, TaskState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("migrate")

# 구버전 상태 → 새 TaskState 매핑
STATE_MAP = {
    # 구버전 중국식 키
    "Taizi": TaskState.SejaFinalReview,
    "Zhongshu": TaskState.HongmungwanDraft,
    "Menxia": TaskState.SaganwonFinalReview,
    "Assigned": TaskState.SeungjeongwonAssigned,
    "Next": TaskState.Ready,
    "Doing": TaskState.InProgress,
    "Review": TaskState.FinalReview,
    "Done": TaskState.Completed,
    "Blocked": TaskState.Blocked,
    "Cancelled": TaskState.Cancelled,
    "Pending": TaskState.Pending,
    # Fallback
    "Inbox": TaskState.SejaFinalReview,
    "": TaskState.SejaFinalReview,
    # 중간 마이그레이션 키와 최종 키 모두 허용
    "SejaReview": TaskState.SejaFinalReview,
    "SejaFinalReview": TaskState.SejaFinalReview,
    "HongmungwanDraft": TaskState.HongmungwanDraft,
    "SaganwonReview": TaskState.SaganwonFinalReview,
    "SaganwonFinalReview": TaskState.SaganwonFinalReview,
    "SeungjeongwonAssigned": TaskState.SeungjeongwonAssigned,
    "Ready": TaskState.Ready,
    "InProgress": TaskState.InProgress,
    "FinalReview": TaskState.FinalReview,
    "Completed": TaskState.Completed,
    "PendingConfirm": TaskState.PendingConfirm,
}


def parse_old_task(old: dict) -> dict:
    """구버전 task JSON을 Edict Task 파라미터로 변환."""
    state_str = old.get("state", "SejaFinalReview")
    state = STATE_MAP.get(state_str, TaskState.SejaFinalReview)

    legacy_id = old.get("id", "")
    title = old.get("title", "미명 업무")

    # 解析时间
    updated_str = old.get("updatedAt", "")
    try:
        updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        updated_at = datetime.now(timezone.utc)

    return {
        "trace_id": str(uuid.uuid4()),
        "title": title,
        "description": old.get("now", ""),
        "priority": "중",
        "state": state,
        "assignee_org": old.get("org", None),
        "creator": old.get("official", "emperor"),
        "tags": [legacy_id] if legacy_id else [],
        "org": old.get("org", Task.org_for_state(state)),
        "official": old.get("official", ""),
        "now": old.get("now", ""),
        "eta": old.get("eta", "-"),
        "block": old.get("block", "없음"),
        "output": old.get("output", ""),
        "archived": bool(old.get("archived", False)),
        "flow_log": old.get("flow_log", []),
        "progress_log": old.get("progress_log", []),
        "todos": old.get("todos", []),
        "scheduler": old.get("scheduler", {}),
        "template_id": old.get("templateId", ""),
        "template_params": old.get("templateParams", {}),
        "ac": old.get("ac", ""),
        "target_dept": old.get("targetDept", ""),
        "meta": {
            "legacy_id": legacy_id,
            "legacy_state": state_str,
            "legacy_output": old.get("output", ""),
            "legacy_ac": old.get("ac", ""),
            "legacy_eta": old.get("eta", ""),
            "legacy_block": old.get("block", ""),
        },
        "created_at": updated_at,  # 구버전에 created_at 없음, updated_at으로 근사
        "updated_at": updated_at,
    }


async def migrate(file_path: Path, dry_run: bool = False):
    """마이그레이션 실행."""
    if not file_path.exists():
        log.error(f"데이터 파일이 없습니다: {file_path}")
        return

    raw = file_path.read_text(encoding="utf-8")
    old_tasks = json.loads(raw)
    log.info(f"구버전 업무 {len(old_tasks)}건 읽기 완료")

    # 统计
    stats = {"total": len(old_tasks), "migrated": 0, "skipped": 0, "errors": 0}
    by_state = {}

    for old in old_tasks:
        state_str = old.get("state", "?")
        by_state[state_str] = by_state.get(state_str, 0) + 1

    log.info(f"상태 분포: {by_state}")

    if dry_run:
        log.info("=== DRY RUN 모덱，데이터베이스에 기록하지 않음 ===")
        for old in old_tasks:
            params = parse_old_task(old)
            log.info(f"  [{params['meta']['legacy_id']}] {params['title'][:40]} → {params['state'].value}")
        log.info(f"시험 실행 완료: {stats['total']} 개 작업 대기 중")
        return

    # Postgres 기록
    async with async_session() as db:
        for old in old_tasks:
            try:
                params = parse_old_task(old)
                legacy_id = params["meta"]["legacy_id"]

                # 이미 마이그레이션 여부 확인
                from sqlalchemy import select
                existing = await db.execute(
                    select(Task).where(Task.tags.contains([legacy_id]))
                )
                if existing.scalars().first():
                    log.debug(f"건너뛰기: {legacy_id}")
                    stats["skipped"] += 1
                    continue

                task = Task(**params)
                db.add(task)
                stats["migrated"] += 1
                log.info(f"✅ 마이그레이션: [{legacy_id}] {params['title'][:40]} → {params['state'].value}")

            except Exception as e:
                log.error(f"❌ 마이그레이션 실패: {old.get('id', '?')}: {e}")
                stats["errors"] += 1

        await db.commit()

    log.info(f"마이그레이션 완료: 총계 {stats['total']}, 성공 {stats['migrated']}, "
             f"건너뜀 {stats['skipped']}, 오류 {stats['errors']}")


def main():
    parser = argparse.ArgumentParser(description="Migrate JSON tasks to Postgres")
    parser.add_argument(
        "--file", "-f",
        default=str(Path(__file__).parent.parent.parent / "data" / "tasks_source.json"),
        help="Path to tasks_source.json",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only analyze, don't write")
    args = parser.parse_args()

    asyncio.run(migrate(Path(args.file), dry_run=args.dry_run))


if __name__ == "__main__":
    main()
