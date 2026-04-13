# app/core/redis_client.py — Redis blacklist check (read-only, mirrors auth-service)
import hashlib
import logging
from .config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not settings.REDIS_URL:
        return None
    try:
        import redis
        c = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=1,
            socket_connect_timeout=1,
        )
        c.ping()
        _client = c
        logger.info("Redis connected (blacklist check)")
        return _client
    except Exception as exc:
        logger.warning("Redis unavailable — blacklist check disabled (%s)", exc)
        return None


def is_blacklisted(token: str) -> bool:
    """Return True if token has been blacklisted by auth-service."""
    client = _get_client()
    if client is None:
        return False
    try:
        digest = hashlib.sha256(token.encode()).hexdigest()
        return client.exists(f"blacklist:{digest}") == 1
    except Exception as exc:
        logger.error("Blacklist check error: %s", exc)
        return False
