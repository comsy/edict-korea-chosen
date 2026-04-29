"""EventBus 테스트 — fakeredis 사용."""
import json

import pytest

from app.services.event_bus import (
    STREAM_PREFIX,
    EventBus,
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_COMPLETED,
)


class TestStreamKey:
    def test_stream_key_includes_prefix_and_topic(self, event_bus):
        key = event_bus._stream_key(TOPIC_TASK_CREATED)
        assert key == f"{STREAM_PREFIX}{TOPIC_TASK_CREATED}"

    def test_stream_key_different_topics_differ(self, event_bus):
        assert event_bus._stream_key(TOPIC_TASK_CREATED) != event_bus._stream_key(TOPIC_TASK_STATUS)


class TestPublish:
    async def test_publish_returns_entry_id(self, event_bus):
        entry_id = await event_bus.publish(
            topic=TOPIC_TASK_CREATED,
            trace_id="trace-001",
            event_type="task.created",
            producer="task_service",
            payload={"task_id": "abc"},
        )
        assert entry_id is not None
        assert "-" in str(entry_id)

    async def test_publish_stores_payload_as_json(self, event_bus):
        await event_bus.publish(
            topic=TOPIC_TASK_STATUS,
            trace_id="trace-002",
            event_type="task.status",
            producer="test",
            payload={"task_id": "xyz", "state": "InProgress"},
        )
        stream_key = event_bus._stream_key(TOPIC_TASK_STATUS)
        messages = await event_bus.redis.xrange(stream_key)
        assert len(messages) == 1
        data = messages[0][1]
        payload = json.loads(data["payload"])
        assert payload["task_id"] == "xyz"

    async def test_publish_includes_required_fields(self, event_bus):
        await event_bus.publish(
            topic=TOPIC_TASK_CREATED,
            trace_id="trace-003",
            event_type="task.created",
            producer="svc",
        )
        stream_key = event_bus._stream_key(TOPIC_TASK_CREATED)
        messages = await event_bus.redis.xrange(stream_key)
        data = messages[0][1]
        for field in ("event_id", "trace_id", "timestamp", "topic", "event_type", "producer"):
            assert field in data, f"Missing field: {field}"


class TestConsume:
    async def test_consume_returns_published_event(self, event_bus):
        await event_bus.ensure_consumer_group(TOPIC_TASK_CREATED, "grp1")
        await event_bus.publish(
            topic=TOPIC_TASK_CREATED,
            trace_id="t1",
            event_type="task.created",
            producer="svc",
            payload={"task_id": "t1"},
        )
        events = await event_bus.consume(TOPIC_TASK_CREATED, "grp1", "consumer1", block_ms=100)
        assert len(events) == 1
        entry_id, data = events[0]
        assert data["event_type"] == "task.created"
        assert data["payload"]["task_id"] == "t1"

    async def test_consume_payload_is_deserialized(self, event_bus):
        await event_bus.ensure_consumer_group(TOPIC_TASK_STATUS, "grp2")
        await event_bus.publish(
            topic=TOPIC_TASK_STATUS,
            trace_id="t2",
            event_type="task.status",
            producer="svc",
            payload={"key": "value", "num": 42},
        )
        events = await event_bus.consume(TOPIC_TASK_STATUS, "grp2", "c1", block_ms=100)
        assert len(events) == 1
        _, data = events[0]
        assert isinstance(data["payload"], dict)
        assert data["payload"]["num"] == 42

    async def test_consume_empty_stream_returns_empty_list(self, event_bus):
        await event_bus.ensure_consumer_group(TOPIC_TASK_COMPLETED, "grp3")
        events = await event_bus.consume(TOPIC_TASK_COMPLETED, "grp3", "c1", block_ms=100)
        assert events == []

    async def test_ack_prevents_redelivery(self, event_bus):
        await event_bus.ensure_consumer_group(TOPIC_TASK_CREATED, "grp-ack")
        await event_bus.publish(
            topic=TOPIC_TASK_CREATED, trace_id="ta", event_type="e", producer="p"
        )
        events = await event_bus.consume(TOPIC_TASK_CREATED, "grp-ack", "c1", block_ms=100)
        entry_id, _ = events[0]
        await event_bus.ack(TOPIC_TASK_CREATED, "grp-ack", entry_id)

        pending = await event_bus.get_pending(TOPIC_TASK_CREATED, "grp-ack")
        assert len(pending) == 0


class TestPublishBatch:
    async def test_batch_returns_all_entry_ids(self, event_bus):
        batch = [
            {"topic": TOPIC_TASK_CREATED, "trace_id": "b1", "event_type": "e1", "producer": "p", "payload": {}},
            {"topic": TOPIC_TASK_STATUS, "trace_id": "b2", "event_type": "e2", "producer": "p", "payload": {}},
        ]
        ids = await event_bus.publish_batch(batch)
        assert len(ids) == 2

    async def test_batch_events_appear_in_streams(self, event_bus):
        batch = [
            {"topic": TOPIC_TASK_CREATED, "trace_id": "bb1", "event_type": "e", "producer": "p"},
            {"topic": TOPIC_TASK_CREATED, "trace_id": "bb2", "event_type": "e", "producer": "p"},
        ]
        await event_bus.publish_batch(batch)
        stream_key = event_bus._stream_key(TOPIC_TASK_CREATED)
        messages = await event_bus.redis.xrange(stream_key)
        assert len(messages) == 2


class TestConsumeMulti:
    async def test_consume_multi_from_multiple_topics(self, event_bus):
        topics = [TOPIC_TASK_CREATED, TOPIC_TASK_STATUS]
        for t in topics:
            await event_bus.ensure_consumer_group(t, "multi-grp")

        await event_bus.publish(topic=TOPIC_TASK_CREATED, trace_id="m1", event_type="e1", producer="p")
        await event_bus.publish(topic=TOPIC_TASK_STATUS, trace_id="m2", event_type="e2", producer="p")

        events = await event_bus.consume_multi(topics, "multi-grp", "c1", block_ms=100)
        assert len(events) == 2
        received_topics = {ev[0] for ev in events}
        assert TOPIC_TASK_CREATED in received_topics
        assert TOPIC_TASK_STATUS in received_topics

    async def test_consume_multi_empty_returns_empty(self, event_bus):
        topics = [TOPIC_TASK_COMPLETED]
        await event_bus.ensure_consumer_group(TOPIC_TASK_COMPLETED, "multi-empty")
        events = await event_bus.consume_multi(topics, "multi-empty", "c1", block_ms=100)
        assert events == []


class TestEnsureConsumerGroup:
    async def test_ensure_consumer_group_idempotent(self, event_bus):
        # 두 번 호출해도 에러 없어야 함 (BUSYGROUP 처리)
        await event_bus.ensure_consumer_group(TOPIC_TASK_CREATED, "idempotent-grp")
        await event_bus.ensure_consumer_group(TOPIC_TASK_CREATED, "idempotent-grp")
