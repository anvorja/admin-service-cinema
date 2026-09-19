# app/core/redis_client.py — Redis blacklist check (read-only, mirrors auth-service)
# + caché corta de perfiles de user-service (ver ARCHITECTURE.md, "Aislamiento
# de base de datos por servicio", caso 2): evita llamar por HTTP a
# user-service en cada request del panel admin para resolver auth/rol.
import hashlib
import json
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


def get_cached_user_profile(email: str) -> dict | None:
    """Perfil de user-service cacheado por email (TTL corto, ver set_cached_user_profile)."""
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(f"user-profile:{email}")
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.error("User-profile cache read error: %s", exc)
        return None


def set_cached_user_profile(email: str, data: dict, ttl: int = 60) -> None:
    """
    TTL corto (default 60s) a propósito: es una caché de conveniencia para no
    llamar a user-service en cada request del panel admin, no una fuente de
    verdad — si un admin desactiva a alguien, el efecto tarda como máximo
    ese TTL en reflejarse en el propio estado de sesión de ese usuario.
    """
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(f"user-profile:{email}", ttl, json.dumps(data, default=str))
    except Exception as exc:
        logger.error("User-profile cache write error: %s", exc)
