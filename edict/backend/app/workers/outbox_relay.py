"""Outbox Relay Worker — outbox_events 테이블을 폴링하여 미발행 이벤트를 Redis Streams로 전달.

트랜잭션 기반 Outbox 패턴의 전달 단계:
- 트랜잭션 계층이 이벤트를 outbox 테이블에 기록 (비즈니스 데이터와 동일 트랜잭션)
- 본 worker가 미발행 이벤트를 폴링하여 EventBus.publish로 Redis에 전달
- 전달 성공 시 published=True 표시; 실패 시 attempts 누적, 상한 도달 시 DLQ로 이동
- 소비자는 event_id로 멱등성 보장, relay 재시작 시 중복 전달 방지
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone

from sqlalchemy import select, update

from ..db import async_session
from ..models.outbox import OutboxEvent
from ..services.event_bus import EventBus

log = logging.getLogger("edict.outbox_relay")

MAX_ATTEMPTS = 5
BATCH_SIZE = 50
POLL_INTERVAL = 1.0  # 초


class OutboxRelay:
    """outbox_events 테이블을 폴링하여 Redis Streams로 전달."""

    def __init__(self):
        self.bus = EventBus()
        self._running = False

    async def start(self):
        await self.bus.connect()
        self._running = True
        log.info("🚀 Outbox Relay started")

        while self._running:
            try:
                relayed = await self._relay_cycle()
                if relayed == 0:
                    await asyncio.sleep(POLL_INTERVAL)
            except Exception as e:
                log.error(f"Outbox relay error: {e}", exc_info=True)
                await asyncio.sleep(POLL_INTERVAL * 2)

    async def stop(self):
        self._running = False
        await self.bus.close()
        log.info("Outbox Relay stopped")

    async def _relay_cycle(self) -> int:
        """미전달 이벤트 배치 처리. 본 회차 처리 건수 반환."""
        async with async_session() as db:
            # FOR UPDATE SKIP LOCKED로 다수 relay 인스턴스 병렬 실행 허용
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.published == False)  # noqa: E712
                .order_by(OutboxEvent.id)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
            result = await db.execute(stmt)
            events = list(result.scalars().all())

            if not events:
                return 0

            for event in events:
                try:
                    await self.bus.publish(
                        topic=event.topic,
                        trace_id=event.trace_id,
                        event_type=event.event_type,
                        producer=event.producer,
                        payload=event.payload or {},
                        meta=event.meta or {},
                    )
                    event.published = True
                    event.published_at = datetime.now(timezone.utc)
                    log.debug(f"📤 Relayed outbox #{event.id} → {event.topic}")

                except Exception as exc:
                    event.attempts += 1
                    event.last_error = str(exc)[:500]
                    log.warning(
                        f"Outbox #{event.id} relay failed (attempt {event.attempts}): {exc}"
                    )

                    if event.attempts >= MAX_ATTEMPTS:
                        # DLQ로 전달
                        try:
                            await self.bus.publish(
                                topic="dead_letter",
                                trace_id=event.trace_id,
                                event_type="outbox.dead_letter",
                                producer="outbox_relay",
                                payload={
                                    "outbox_id": event.id,
                                    "event_id": event.event_id,
                                    "topic": event.topic,
                                    "event_type": event.event_type,
                                    "payload": event.payload,
                                    "error": event.last_error,
                                    "attempts": event.attempts,
                                },
                            )
                        except Exception as dlq_err:
                            log.error(f"Failed to publish DLQ for outbox #{event.id}: {dlq_err}")

            await db.commit()
            return len(events)


async def run_outbox_relay():
    """진입 함수 — worker를 직접 실행하기 위함."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    relay = OutboxRelay()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(relay.stop()))

    await relay.start()


if __name__ == "__main__":
    asyncio.run(run_outbox_relay())
