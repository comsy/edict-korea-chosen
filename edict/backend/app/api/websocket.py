"""WebSocket 엔드포인트 — 프론트엔드로 이벤트 실시간 푸시.

기존 아키텍처의 5초 HTTP 폴링을 대체:
- 클라이언트 WebSocket 연결
- 서버 측 Redis Pub/Sub 채널 구독
- 실시간 이벤트 푸시 (상태 변경, Agent 사고 흐름, 하트비트 등)
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import get_settings
from ..services.event_bus import get_event_bus

log = logging.getLogger("edict.ws")
router = APIRouter()

# 활성 연결 관리
_connections: set[WebSocket] = set()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """주 WebSocket 엔드포인트 — 모든 이벤트 푸시."""
    await ws.accept()
    _connections.add(ws)
    log.info(f"WebSocket connected. Total: {len(_connections)}")

    # 독립적인 Redis Pub/Sub 연결 생성
    settings = get_settings()
    pubsub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = pubsub_redis.pubsub()

    # 모든 edict 채널 구독
    await pubsub.psubscribe("edict:pubsub:*")

    try:
        # 병행: Redis Pub/Sub 리스닝 + 클라이언트 메시지 처리
        await asyncio.gather(
            _relay_events(pubsub, ws),
            _handle_client_messages(ws),
        )
    except WebSocketDisconnect:
        log.info("WebSocket disconnected")
    except Exception as e:
        log.error(f"WebSocket error: {e}")
    finally:
        _connections.discard(ws)
        await pubsub.punsubscribe("edict:pubsub:*")
        await pubsub_redis.aclose()
        log.info(f"WebSocket cleaned up. Remaining: {len(_connections)}")


async def _relay_events(pubsub, ws: WebSocket):
    """Redis Pub/Sub에서 이벤트 수신, WebSocket으로 푸시."""
    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel = message["channel"]
            data = message["data"]

            # topic 이름 추출
            topic = channel.replace("edict:pubsub:", "") if channel.startswith("edict:pubsub:") else channel

            try:
                event_data = json.loads(data) if isinstance(data, str) else data
                await ws.send_json({
                    "type": "event",
                    "topic": topic,
                    "data": event_data,
                })
            except Exception as e:
                log.warning(f"Failed to relay event: {e}")
                break


async def _handle_client_messages(ws: WebSocket):
    """클라이언트가 보낸 메시지 처리 (하트비트, 구독 필터 등)."""
    while True:
        try:
            data = await ws.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
            elif msg_type == "subscribe":
                # 프론트엔드가 특정 topic만 구독 요청 (미래 확장)
                topics = data.get("topics", [])
                log.debug(f"Client subscribe request: {topics}")
                await ws.send_json({"type": "subscribed", "topics": topics})
            else:
                log.debug(f"Unknown client message: {msg_type}")
        except WebSocketDisconnect:
            raise
        except Exception:
            break


@router.websocket("/ws/task/{task_id}")
async def task_websocket(ws: WebSocket, task_id: str):
    """단일 작업 WebSocket — 특정 작업과 관련된 이벤트만 푸시."""
    await ws.accept()
    _connections.add(ws)

    settings = get_settings()
    pubsub_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = pubsub_redis.pubsub()
    await pubsub.psubscribe("edict:pubsub:*")

    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                data = message["data"]
                try:
                    event_data = json.loads(data) if isinstance(data, str) else data
                    payload = event_data.get("payload", {})
                    if isinstance(payload, str):
                        payload = json.loads(payload)

                    # 이 작업과 관련된 이벤트만 전달
                    if payload.get("task_id") == task_id:
                        topic = message["channel"].replace("edict:pubsub:", "")
                        await ws.send_json({
                            "type": "event",
                            "topic": topic,
                            "data": event_data,
                        })
                except Exception:
                    continue
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(ws)
        await pubsub.punsubscribe("edict:pubsub:*")
        await pubsub_redis.aclose()


async def broadcast(event: dict):
    """연결된 모든 WebSocket 클라이언트에 이벤트 브로드캐스트 (서버 내부 호출용)."""
    dead = set()
    for ws in _connections:
        try:
            await ws.send_json(event)
        except Exception:
            dead.add(ws)
    _connections -= dead
