"""Bus event agent-run via Redis pub/sub (PRD §7 — SSE run LangGraph live).

Runner (proses Celery/thread) MEMPUBLIKASIKAN progres node graph; endpoint SSE
(proses API) BERLANGGANAN dan meneruskannya ke browser. Redis sudah jadi broker
Celery, jadi tanpa dependensi baru. Publikasi bersifat best-effort — kegagalan bus
tak boleh menggagalkan analisis.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from core.config import get_settings

CHANNEL = "agent_events"


def publish_agent_event(payload: dict) -> None:
    """Publikasikan satu event (sinkron; dipanggil dari runner). Best-effort."""
    try:
        import redis

        r = redis.from_url(get_settings().redis_url)
        r.publish(CHANNEL, json.dumps(payload, default=str))
        r.close()
    except Exception:
        pass  # bus event opsional — jangan pernah menggagalkan pekerjaan pemanggil


async def subscribe_agent_events(heartbeat: float = 15.0) -> AsyncIterator[str]:
    """Aliran baris SSE ('data: {...}\\n\\n') dari channel; ping berkala jaga koneksi."""
    import redis.asyncio as aioredis

    r = aioredis.from_url(get_settings().redis_url)
    ps = r.pubsub()
    await ps.subscribe(CHANNEL)
    try:
        yield 'data: {"type":"hello"}\n\n'
        while True:
            msg = await ps.get_message(ignore_subscribe_messages=True, timeout=heartbeat)
            if msg and msg.get("type") == "message":
                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield f"data: {data}\n\n"
            else:
                yield ": ping\n\n"  # heartbeat (komentar SSE, diabaikan klien)
    finally:
        try:
            await ps.unsubscribe(CHANNEL)
            await ps.aclose()
            await r.aclose()
        except Exception:
            pass
