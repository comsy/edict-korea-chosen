"""Orchestrator Worker — 이벤트 버스를 소비하여 업무 상태 머신 구동.

주제 리스닝:
- task.created → 자동으로 세자 agent에 파견
- task.status → 다양한 상태 변경 처리, 하위 agent에 자동 파견
- task.completed → 업무 완료 로그 기록
- task.stalled → 정체된 업무 처리 (재시도 → 승격 → 차단)

부가 타이머 작업:
- _check_stalled → 60초마다 InProgress 상태 타임아웃 업무 스캔, task.stalled 이벤트 발행

이것은 시스템의 핵심 오케스트레이터로, 기존 아키텍처의 daemon 스레드 + 정기 스캔 역할을 대체.
Redis Streams ACK 메커니즘 덕분에: worker가 크래시되어도 ACK되지 않은 이벤트는
다른 컨슈머가 자동으로 인계받아 절대 유실되지 않음.
"""

import asyncio
import logging
import signal
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from ..config import get_settings
from ..db import async_session
from ..models.task import TaskState, STATE_AGENT_MAP, ORG_AGENT_MAP
from ..services.event_bus import (
    EventBus,
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_DISPATCH,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_STALLED,
    TOPIC_TASK_ESCALATED,
)
from ..services.task_service import TaskService

log = logging.getLogger("edict.orchestrator")

GROUP = "orchestrator"
CONSUMER = "orch-1"

# 정체 복구 설정
MAX_STALL_RETRIES = 2        # 최대 재시도 횟수
MAX_ESCALATION_LEVEL = 3     # 최대 승격 단계
STALL_RETRY_BACKOFF = [30, 60, 120]  # 재시도 백오프 시간(초)

# 정체 감지 설정
STALL_CHECK_INTERVAL_SEC = 60   # 확인 간격(초)
STALL_THRESHOLD_SEC = 600       # 10분 이상 하트비트 없으면 정체로 간주

# 승격 경로: 특정 부서에서 막혔을 때 상급으로 승격
_ESCALATION_PATH = {
    "InProgress": TaskState.SeungjeongwonAssigned,   # 육조가 막힘 → 승정원으로 반송하여 재배분
    "Ready": TaskState.SeungjeongwonAssigned,
    "SeungjeongwonAssigned": TaskState.SaganwonFinalReview,  # 승정원이 막힘 → 사간원으로 반송하여 재검토
    "SaganwonFinalReview": TaskState.HongmungwanDraft,  # 사간원이 막힘 → 홍문관으로 반송하여 재기안
    "HongmungwanDraft": TaskState.SejaFinalReview,   # 홍문관이 막힘 → 세자로 반송하여 재작성
}

# 需要监听的 topics
WATCHED_TOPICS = [
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_STALLED,
]


class OrchestratorWorker:
    """事件驱动的编排器 Worker。"""

    def __init__(self):
        self.bus = EventBus()
        self._running = False
        self._stall_checker_task: asyncio.Task | None = None

    async def start(self):
        """启动 worker 主循环。"""
        await self.bus.connect()

        # 确保所有消费者组
        for topic in WATCHED_TOPICS:
            await self.bus.ensure_consumer_group(topic, GROUP)

        self._running = True
        log.info("🏛️ Orchestrator worker started")

        # 先处理崩溃遗留的 pending 事件
        await self._recover_pending()

        # 启动停滞检测后台任务
        self._stall_checker_task = asyncio.create_task(self._stall_check_loop())

        while self._running:
            try:
                await self._poll_cycle()
            except Exception as e:
                log.error(f"Orchestrator poll error: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def stop(self):
        self._running = False
        if self._stall_checker_task:
            self._stall_checker_task.cancel()
        await self.bus.close()
        log.info("Orchestrator worker stopped")

    async def _recover_pending(self):
        """恢复崩溃前未 ACK 的事件。"""
        for topic in WATCHED_TOPICS:
            events = await self.bus.claim_stale(
                topic, GROUP, CONSUMER, min_idle_ms=30000, count=50
            )
            if events:
                log.info(f"Recovering {len(events)} stale events from {topic}")
                for entry_id, event in events:
                    await self._handle_event(topic, entry_id, event)

    async def _poll_cycle(self):
        """一次轮询周期：多 topic 同时消费，按 task_id 分组并行处理。"""
        events = await self.bus.consume_multi(
            WATCHED_TOPICS, GROUP, CONSUMER, count=20, block_ms=500
        )
        if not events:
            return

        # 按 task_id 分组：同一任务串行，不同任务并行
        by_task: dict[str, list[tuple[str, str, dict]]] = {}
        for topic, entry_id, event in events:
            task_id = event.get("payload", {}).get("task_id", entry_id)
            by_task.setdefault(task_id, []).append((topic, entry_id, event))

        async def _process_task_events(task_events: list[tuple[str, str, dict]]):
            for topic, entry_id, event in task_events:
                try:
                    await self._handle_event(topic, entry_id, event)
                    await self.bus.ack(topic, GROUP, entry_id)
                except Exception as e:
                    log.error(
                        f"Error handling event {entry_id} from {topic}: {e}",
                        exc_info=True,
                    )

        await asyncio.gather(*[
            _process_task_events(evts) for evts in by_task.values()
        ])

    async def _handle_event(self, topic: str, entry_id: str, event: dict):
        """根据 topic 和 event_type 分发处理。"""
        event_type = event.get("event_type", "")
        trace_id = event.get("trace_id", "")
        payload = event.get("payload", {})

        log.info(f"📨 {topic}/{event_type} trace={trace_id}")

        if topic == TOPIC_TASK_CREATED:
            await self._on_task_created(payload, trace_id)
        elif topic == TOPIC_TASK_STATUS:
            await self._on_task_status(event_type, payload, trace_id)
        elif topic == TOPIC_TASK_COMPLETED:
            await self._on_task_completed(payload, trace_id)
        elif topic == TOPIC_TASK_STALLED:
            await self._on_task_stalled(payload, trace_id)

    async def _on_task_created(self, payload: dict, trace_id: str):
        """업무 생성 → 세자 agent에 파견하여 기안 작성."""
        task_id = payload.get("task_id")
        state = payload.get("state", "SejaFinalReview")
        agent = STATE_AGENT_MAP.get(TaskState(state), "seja")

        await self.bus.publish(
            topic=TOPIC_TASK_DISPATCH,
            trace_id=trace_id,
            event_type="task.dispatch.request",
            producer="orchestrator",
            payload={
                "task_id": task_id,
                "agent": agent,
                "state": state,
                "message": f"新任务已创建: {payload.get('title', '')}",
            },
        )

    async def _on_task_status(self, event_type: str, payload: dict, trace_id: str):
        """상태 변경 → 자동으로 다음 agent에 파견."""
        task_id = payload.get("task_id")
        new_state_str = payload.get("to", "")

        try:
            new_state = TaskState(new_state_str)
        except ValueError:
            log.warning(f"Unknown state: {new_state_str}")
            return

        # 새 상태에 해당하는 agent가 있으면 자동 파견
        agent = STATE_AGENT_MAP.get(new_state)

        # SeungjeongwonAssigned 상태로 진입 시, 육조 해당 agent 찾기
        if new_state == TaskState.SeungjeongwonAssigned:
            org = payload.get("assignee_org", "")
            if org:
                agent = ORG_AGENT_MAP.get(org, agent)
            else:
                # assignee_org가 비어있으면 대상 부서 결정 불가
                # 승정원에 파견하여 배분 결정
                log.warning(
                    f"Task {task_id} entering SeungjeongwonAssigned without assignee_org, "
                    f"dispatching to seungjeongwon for manual routing"
                )
                agent = "seungjeongwon"

        if agent:
            await self.bus.publish(
                topic=TOPIC_TASK_DISPATCH,
                trace_id=trace_id,
                event_type="task.dispatch.request",
                producer="orchestrator",
                payload={
                    "task_id": task_id,
                    "agent": agent,
                    "state": new_state_str,
                    "message": f"任务已流转到 {new_state_str}",
                },
            )

    async def _on_task_completed(self, payload: dict, trace_id: str):
        """작업 완료 → 记录日志。"""
        task_id = payload.get("task_id")
        log.info(f"🎉 Task {task_id} completed. trace={trace_id}")

    async def _on_task_stalled(self, payload: dict, trace_id: str):
        """任务停滞 → 自动重试或升级。

        恢复策略：
        1. 첫 번째 정체：현재 상태에서 agent 재발송(재시도)
        2. 重试耗尽：向上级升级（如六部→승정원→사간원）
        3. 升级到顶（세자）仍失败：标记 Blocked + 通知人工介入
        """
        task_id = payload.get("task_id")
        current_state = payload.get("state", "")
        stall_count = int(payload.get("stall_count", 0))
        escalation_level = int(payload.get("escalation_level", 0))

        log.warning(
            f"⏸️ Task {task_id} stalled! state={current_state} "
            f"stall_count={stall_count} escalation={escalation_level} trace={trace_id}"
        )

        # 전략 1: 재시도 — 재시도 횟수를 초과하지 않았을 때, 동일 agent에 재파견
        if stall_count < MAX_STALL_RETRIES:
            agent = STATE_AGENT_MAP.get(TaskState(current_state)) if current_state else None
            if current_state in ("InProgress", "Ready"):
                org = payload.get("assignee_org", "")
                agent = ORG_AGENT_MAP.get(org, agent)

            if agent:
                log.info(f"🔄 Retrying task {task_id} → agent '{agent}' (attempt {stall_count + 1})")
                await self.bus.publish(
                    topic=TOPIC_TASK_DISPATCH,
                    trace_id=trace_id,
                    event_type="task.dispatch.retry",
                    producer="orchestrator",
                    payload={
                        "task_id": task_id,
                        "agent": agent,
                        "state": current_state,
                        "message": f"업무 정체 재시도 (제{stall_count + 1}회)",
                        "stall_count": stall_count + 1,
                    },
                )
                return

        # 전략 2: 승격 — 재시도 소진, 상급으로 전이
        if escalation_level < MAX_ESCALATION_LEVEL:
            escalate_to = _ESCALATION_PATH.get(current_state)
            if escalate_to:
                escalate_agent = STATE_AGENT_MAP.get(escalate_to, "seungjeongwon")
                log.info(
                    f"⬆️ Escalating task {task_id}: {current_state} → {escalate_to.value} "
                    f"(level {escalation_level + 1})"
                )
                await self.bus.publish(
                    topic=TOPIC_TASK_ESCALATED,
                    trace_id=trace_id,
                    event_type="task.escalated",
                    producer="orchestrator",
                    payload={
                        "task_id": task_id,
                        "from_state": current_state,
                        "to_state": escalate_to.value,
                        "escalation_level": escalation_level + 1,
                        "reason": f"任务在 {current_state} 停滞，升级处理",
                    },
                )
                # 派发给上级 agent
                await self.bus.publish(
                    topic=TOPIC_TASK_DISPATCH,
                    trace_id=trace_id,
                    event_type="task.dispatch.escalation",
                    producer="orchestrator",
                    payload={
                        "task_id": task_id,
                        "agent": escalate_agent,
                        "state": escalate_to.value,
                        "message": f"下级停滞，需上级介入 (从 {current_state} 升级)",
                        "escalation_level": escalation_level + 1,
                    },
                )
                return

        # 策略 3: 所有升级耗尽 → 标记 Blocked，等待人工介入
        log.error(
            f"🚨 Task {task_id} exhausted all recovery options! "
            f"Marking as Blocked. Manual intervention required."
        )
        await self.bus.publish(
            topic=TOPIC_TASK_STATUS,
            trace_id=trace_id,
            event_type="task.state.Blocked",
            producer="orchestrator",
            payload={
                "task_id": task_id,
                "from": current_state,
                "to": TaskState.Blocked.value,
                "reason": f"任务多次停滞（重试{MAX_STALL_RETRIES}次+升级{MAX_ESCALATION_LEVEL}级），需人工介入",
                "assignee_org": payload.get("assignee_org", ""),
            },
        )

    # ── 정체 업무 감지기 ──

    async def _stall_check_loop(self):
        """정기적으로 InProgress/Ready 상태 타임아웃 업무를 스캔, task.stalled 이벤트 발행."""
        while self._running:
            try:
                await asyncio.sleep(STALL_CHECK_INTERVAL_SEC)
                await self._check_stalled()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Stall check error: {e}", exc_info=True)
                await asyncio.sleep(STALL_CHECK_INTERVAL_SEC)

    async def _check_stalled(self):
        """데이터베이스에서 InProgress/Ready 상태로 임계값을 초과하여 업데이트되지 않은 업무 스캔."""
        threshold = datetime.now(timezone.utc) - timedelta(seconds=STALL_THRESHOLD_SEC)

        async with async_session() as session:
            svc = TaskService(session)
            # 타임아웃 업무 찾기: state in (InProgress, Ready) 및 updated_at < threshold
            from sqlalchemy import select
            from ..models.task import Task
            stmt = select(Task).where(
                Task.state.in_([TaskState.InProgress, TaskState.Ready]),
                Task.updated_at < threshold,
                Task.archived == False,  # noqa: E712
            )
            result = await session.execute(stmt)
            stalled_tasks = result.scalars().all()

        for task in stalled_tasks:
            task_id = str(task.task_id)
            state = task.state.value if isinstance(task.state, TaskState) else str(task.state)
            log.warning(
                f"⏰ Detected stalled task {task_id} in state={state}, "
                f"last updated {task.updated_at}"
            )
            await self.bus.publish(
                topic=TOPIC_TASK_STALLED,
                trace_id=task.trace_id or str(uuid.uuid4()),
                event_type="task.stalled.detected",
                producer="orchestrator.stall_checker",
                payload={
                    "task_id": task_id,
                    "state": state,
                    "assignee_org": task.assignee_org or task.org or "",
                    "stall_count": 0,
                    "escalation_level": 0,
                    "last_updated": task.updated_at.isoformat() if task.updated_at else "",
                },
            )


async def run_orchestrator():
    """入口函数 — 用于直接运行 worker。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    worker = OrchestratorWorker()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))

    await worker.start()


if __name__ == "__main__":
    asyncio.run(run_orchestrator())
