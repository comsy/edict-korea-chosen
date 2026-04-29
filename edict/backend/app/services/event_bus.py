"""Redis Streams 이벤트 버스 — 안정적인 이벤트 발행/소비.

핵심 기능:
- publish: XADD로 스트림에 이벤트 발행
- subscribe: XREADGROUP으로 소비자 그룹 소비, ACK 보장
- ACK되지 않은 이벤트는 소비자 크래시 후 자동 재전달
- 기존 아키텍처 데몬 스레드 손실로 인한 발송 영구 중단의 근본 원인 해결
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from ..config import get_settings

log = logging.getLogger("edict.event_bus")

# ── 표준 Topic 상수 ──
TOPIC_TASK_CREATED = "task.created"
TOPIC_TASK_PLANNING_REQUEST = "task.planning.request"
TOPIC_TASK_PLANNING_COMPLETE = "task.planning.complete"
TOPIC_TASK_REVIEW_REQUEST = "task.review.request"
TOPIC_TASK_REVIEW_RESULT = "task.review.result"
TOPIC_TASK_DISPATCH = "task.dispatch"
TOPIC_TASK_STATUS = "task.status"
TOPIC_TASK_COMPLETED = "task.completed"
TOPIC_TASK_CLOSED = "task.closed"
TOPIC_TASK_REPLAN = "task.replan"
TOPIC_TASK_STALLED = "task.stalled"
TOPIC_TASK_ESCALATED = "task.escalated"

TOPIC_AGENT_THOUGHTS = "agent.thoughts"
TOPIC_AGENT_TODO_UPDATE = "agent.todo.update"
TOPIC_AGENT_HEARTBEAT = "agent.heartbeat"

# 모든 topic에 대응하는 Redis Stream key 접두사
STREAM_PREFIX = "edict:stream:"


class EventBus:
    """Redis Streams 이벤트 버스."""

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url or get_settings().redis_url
        self._redis: aioredis.Redis | None = None

    async def connect(self):
        """Redis 연결 생성."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                max_connections=20,
            )
            log.info(f"EventBus connected to Redis: {self._redis_url}")

    async def close(self):
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    @property
    def redis(self) -> aioredis.Redis:
        assert self._redis is not None, "EventBus not connected. Call connect() first."
        return self._redis

    def _stream_key(self, topic: str) -> str:
        return f"{STREAM_PREFIX}{topic}"

    async def publish(
        self,
        topic: str,
        trace_id: str,
        event_type: str,
        producer: str,
        payload: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> str:
        """Redis Stream에 이벤트 발행.

        Returns:
            event_id (str): Redis가 자동 생성한 Stream entry ID
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "event_type": event_type,
            "producer": producer,
            "payload": json.dumps(payload or {}, ensure_ascii=False),
            "meta": json.dumps(meta or {}, ensure_ascii=False),
        }
        stream_key = self._stream_key(topic)
        entry_id = await self.redis.xadd(stream_key, event, maxlen=10000)
        log.debug(f"📤 Published {topic}/{event_type} → {stream_key} [{entry_id}] trace={trace_id}")

        # 동시에 Pub/Sub 채널로 발행 (WebSocket 실시간 푸시용)
        await self.redis.publish(f"edict:pubsub:{topic}", json.dumps(event, ensure_ascii=False))

        return entry_id

    async def ensure_consumer_group(self, topic: str, group: str):
        """소비자 그룹 존재 확인 (멱등)."""
        stream_key = self._stream_key(topic)
        try:
            await self.redis.xgroup_create(stream_key, group, id="0", mkstream=True)
            log.info(f"Created consumer group {group} on {stream_key}")
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def consume(
        self,
        topic: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[tuple[str, dict]]:
        """소비자 그룹에서 이벤트 소비.

        Returns:
            list of (entry_id, event_dict)
        """
        stream_key = self._stream_key(topic)
        results = await self.redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream_key: ">"},
            count=count,
            block=block_ms,
        )
        events = []
        if results:
            for _stream, messages in results:
                for entry_id, data in messages:
                    # JSON 필드 역직렬화
                    if "payload" in data:
                        data["payload"] = json.loads(data["payload"])
                    if "meta" in data:
                        data["meta"] = json.loads(data["meta"])
                    events.append((entry_id, data))
        return events

    async def ack(self, topic: str, group: str, entry_id: str):
        """소비 확인 — ACK 후 이벤트는 재전달되지 않음."""
        stream_key = self._stream_key(topic)
        await self.redis.xack(stream_key, group, entry_id)
        log.debug(f"✅ ACK {stream_key} [{entry_id}] group={group}")

    async def get_pending(self, topic: str, group: str, count: int = 10) -> list:
        """ACK되지 않은 pending 이벤트 조회 (진단 및 복구용)."""
        stream_key = self._stream_key(topic)
        return await self.redis.xpending_range(stream_key, group, min="-", max="+", count=count)

    async def claim_stale(
        self,
        topic: str,
        group: str,
        consumer: str,
        min_idle_ms: int = 60000,
        count: int = 10,
    ) -> list[tuple[str, dict]]:
        """타임아웃된 pending 이벤트 청구 (소비자 크래시 복구)."""
        stream_key = self._stream_key(topic)
        results = await self.redis.xautoclaim(
            stream_key, group, consumer, min_idle_time=min_idle_ms, start_id="0-0", count=count
        )
        # xautoclaim returns (next_id, [(id, data), ...], [deleted_ids])
        if results and len(results) >= 2:
            events = []
            for entry_id, data in results[1]:
                if "payload" in data:
                    data["payload"] = json.loads(data["payload"])
                if "meta" in data:
                    data["meta"] = json.loads(data["meta"])
                events.append((entry_id, data))
            return events
        return []

    async def stream_info(self, topic: str) -> dict:
        """Stream 정보 조회 (길이, 소비자 그룹 등)."""
        stream_key = self._stream_key(topic)
        try:
            info = await self.redis.xinfo_stream(stream_key)
            return info
        except aioredis.ResponseError:
            return {}

    async def consume_multi(
        self,
        topics: list[str],
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 2000,
    ) -> list[tuple[str, str, dict]]:
        """여러 topic에서 동시 소비 (단일 XREADGROUP 다중 stream).

        Returns:
            list of (topic, entry_id, event_dict)
        """
        streams = {self._stream_key(t): ">" for t in topics}
        results = await self.redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams=streams,
            count=count,
            block=block_ms,
        )
        events = []
        if results:
            # 역매핑 생성: stream_key → topic
            key_to_topic = {self._stream_key(t): t for t in topics}
            for stream_key, messages in results:
                topic = key_to_topic.get(stream_key, stream_key)
                for entry_id, data in messages:
                    if "payload" in data:
                        data["payload"] = json.loads(data["payload"])
                    if "meta" in data:
                        data["meta"] = json.loads(data["meta"])
                    events.append((topic, entry_id, data))
        return events

    async def publish_batch(
        self,
        events: list[dict],
    ) -> list[str]:
        """이벤트 일괄 발행 (pipeline 모드, RTT 감소).

        각 event dict는 다음을 포함해야 함: topic, trace_id, event_type, producer, payload, meta(선택)
        Returns:
            list of entry_ids
        """
        pipe = self.redis.pipeline(transaction=False)
        for evt in events:
            topic = evt["topic"]
            event_data = {
                "event_id": str(uuid.uuid4()),
                "trace_id": evt["trace_id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "topic": topic,
                "event_type": evt["event_type"],
                "producer": evt["producer"],
                "payload": json.dumps(evt.get("payload", {}), ensure_ascii=False),
                "meta": json.dumps(evt.get("meta", {}), ensure_ascii=False),
            }
            stream_key = self._stream_key(topic)
            pipe.xadd(stream_key, event_data, maxlen=10000)
            pipe.publish(f"edict:pubsub:{topic}", json.dumps(event_data, ensure_ascii=False))
        results = await pipe.execute()
        # 각 이벤트는 2개의 pipeline 명령어(xadd + publish) 생성, entry_id는 짝수 위치
        entry_ids = [results[i] for i in range(0, len(results), 2)]
        log.debug(f"📤 Batch published {len(events)} events")
        return entry_ids

    async def get_delivery_count(self, topic: str, group: str, entry_id: str) -> int:
        """메시지의 누적 전달 횟수 조회."""
        stream_key = self._stream_key(topic)
        # XPENDING <stream> <group> <start> <end> <count>는 각 메시지의 상세 정보 반환
        pending = await self.redis.xpending_range(
            stream_key, group, min=entry_id, max=entry_id, count=1
        )
        if pending:
            # 각 pending 항목 형식: {message_id, consumer, idle_time, delivery_count}
            return pending[0].get("times_delivered", 0)
        return 0


# ── 전역 싱글턴 ──
_bus: EventBus | None = None


async def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
        await _bus.connect()
    return _bus
