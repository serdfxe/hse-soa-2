"""Redis cache service using Cache-Aside pattern with Sentinel."""

import json
import logging
from typing import Any

from redis.asyncio.sentinel import Sentinel

from app.core.config import settings

logger = logging.getLogger(__name__)

_sentinel: Sentinel | None = None


def _get_sentinel() -> Sentinel:
    global _sentinel
    if _sentinel is None:
        hosts = [
            (h.strip().split(":")[0], int(h.strip().split(":")[1]))
            for h in settings.redis_sentinel_hosts.split(",")
        ]
        _sentinel = Sentinel(hosts, socket_timeout=0.5)
    return _sentinel


async def get(key: str) -> Any | None:
    try:
        client = _get_sentinel().master_for(settings.redis_sentinel_master, socket_timeout=0.5)
        raw = await client.get(key)
        if raw is None:
            logger.info("cache miss key=%s", key)
            return None
        logger.info("cache hit key=%s", key)
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Redis get failed key=%s error=%s", key, exc)
        return None


async def set(key: str, value: Any, ttl: int | None = None) -> None:
    try:
        client = _get_sentinel().master_for(settings.redis_sentinel_master, socket_timeout=0.5)
        await client.set(key, json.dumps(value), ex=ttl or settings.redis_ttl_seconds)
    except Exception as exc:
        logger.warning("Redis set failed key=%s error=%s", key, exc)


async def delete(*keys: str) -> None:
    try:
        client = _get_sentinel().master_for(settings.redis_sentinel_master, socket_timeout=0.5)
        await client.delete(*keys)
    except Exception as exc:
        logger.warning("Redis delete failed keys=%s error=%s", keys, exc)
