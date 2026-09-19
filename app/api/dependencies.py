# app/api/dependencies.py
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.core.config import settings
from app.core import redis_client
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Valida el JWT y resuelve el usuario contra user-service (dueño de
    cinema_users) — admin-service ya no consulta esa base directamente
    (ver ARCHITECTURE.md, "Aislamiento de base de datos por servicio",
    caso 2). El resultado se cachea en Redis 60s para no llamar a
    user-service en cada request del panel.
    """
    credentials_exception = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials

    if redis_client.is_blacklisted(token):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token has been invalidated. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_email: str = payload.get("sub")
        if not user_email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    data = redis_client.get_cached_user_profile(user_email)
    if data is None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(
                    f"{settings.USER_SERVICE_URL}/api/v1/users/internal/lookup",
                    params={"email": user_email},
                    headers={"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN},
                )
            except httpx.TransportError:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "user-service no disponible")
        if resp.status_code == status.HTTP_404_NOT_FOUND:
            raise credentials_exception
        if resp.status_code != status.HTTP_200_OK:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Error validando usuario")
        data = resp.json()
        redis_client.set_cached_user_profile(user_email, data, ttl=60)

    if not data.get("is_active"):
        raise credentials_exception
    return User(**data)


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not enough permissions")
    return current_user
