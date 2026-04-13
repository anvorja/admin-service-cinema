# app/core/cache.py — Cache invalidation for catalog (write-only use case)
import json
import logging
from typing import Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class _CacheManager:
    def __init__(self) -> None:
        self._client = None
        self._available: Optional[bool] = None

    def _get_client(self):
        if self._available is False:
            return None
        if self._client is not None:
            return self._client
        if not settings.REDIS_URL:
            self._available = False
            return None
        try:
            import redis
            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=0.5,
                socket_connect_timeout=0.5,
            )
            client.ping()
            self._client = client
            self._available = True
            logger.info("Cache layer connected (Redis)")
            return client
        except Exception as exc:
            self._available = False
            logger.warning("Cache unavailable — invalidation skipped (%s)", exc)
            return None

    def delete_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching pattern (e.g. 'home:*')."""
        client = self._get_client()
        if client is None:
            return
        try:
            keys = client.keys(pattern)
            if keys:
                client.delete(*keys)
                logger.info("Cache invalidated: %d key(s) matching '%s'", len(keys), pattern)
        except Exception as exc:
            logger.warning("Cache invalidation error: %s", exc)

    def is_healthy(self) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            return bool(client.ping())
        except Exception:
            return False


cache = _CacheManager()
