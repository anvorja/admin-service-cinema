# app/services/admin_service.py
#
# Los métodos de teatros reciben la sesión de cinema_admin (dueña de este
# servicio) y publican theater.* para que catalog-service sincronice su
# copia de lectura en cinema_catalog (ver ARCHITECTURE.md, "Aislamiento de
# base de datos por servicio", caso 1).
#
# Los métodos de usuarios y de compras/reportes ya NO reciben sesión de BD:
# cinema_users es de user-service y cinema_booking es de booking-service, se
# consultan por HTTP interno (casos 2 y 3 de la misma decisión).
import logging
from typing import List, Optional, Dict, Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.theater import Theater

logger = logging.getLogger(__name__)

_INTERNAL_HEADERS = {"X-Internal-Token": settings.INTERNAL_SERVICE_TOKEN}


class AdminService:

    # ── Users (HTTP a user-service, dueño de cinema_users) ──────────────────────

    @staticmethod
    async def get_users(
        skip: int = 0,
        limit: int = 20,
        include_inactive: bool = False,
        search: Optional[str] = None,
    ) -> List[User]:
        params: Dict[str, Any] = {"skip": skip, "limit": limit, "include_inactive": include_inactive}
        if search:
            params["search"] = search
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.USER_SERVICE_URL}/api/v1/users/internal",
                params=params,
                headers=_INTERNAL_HEADERS,
            )
        if resp.status_code != status.HTTP_200_OK:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Error al consultar usuarios")
        return [User(**item) for item in resp.json()]

    @staticmethod
    async def get_user_by_id(user_id: int) -> Optional[User]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.USER_SERVICE_URL}/api/v1/users/internal/{user_id}",
                headers=_INTERNAL_HEADERS,
            )
        if resp.status_code == status.HTTP_404_NOT_FOUND:
            return None
        if resp.status_code != status.HTTP_200_OK:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Error al consultar el usuario")
        return User(**resp.json())

    @staticmethod
    async def toggle_user_status(user_id: int, admin_id: int) -> Optional[User]:
        """
        Activa / desactiva un usuario. user-service aplica el cambio en
        cinema_users y publica user.deactivated si corresponde — este
        servicio solo aplica la regla de negocio de que un admin no puede
        desactivarse a sí mismo (la conoce porque conoce al admin autenticado).
        """
        if user_id == admin_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "No puedes deshabilitar tu propia cuenta"
            )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{settings.USER_SERVICE_URL}/api/v1/users/internal/{user_id}/toggle",
                headers=_INTERNAL_HEADERS,
            )
        if resp.status_code == status.HTTP_404_NOT_FOUND:
            return None
        if resp.status_code != status.HTTP_200_OK:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Error al actualizar el usuario")
        return User(**resp.json())

    # ── Theaters (cinema_admin — publica theater.* para catalog-service) ────────

    @staticmethod
    async def create_theater(db: Session, name: str, location: str, description: Optional[str]) -> Theater:
        existing = db.query(Theater).filter(Theater.name == name).first()
        if existing:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Teatro '{name}' ya existe")

        theater = Theater(name=name, location=location, description=description)
        db.add(theater)
        db.commit()
        db.refresh(theater)

        try:
            from app.kafka.producer import publish_event
            await publish_event("theater.created", {
                "theater_id": theater.id,
                "name": theater.name,
                "location": theater.location,
                "description": theater.description,
            }, key=str(theater.id))
        except Exception as e:
            logger.warning("No se pudo publicar theater.created: %s", e)

        return theater

    @staticmethod
    def get_theaters(
        catalog_db: Session,
        skip: int = 0,
        limit: int = 20,
        include_inactive: bool = False,
    ) -> List[Theater]:
        q = catalog_db.query(Theater)
        if not include_inactive:
            q = q.filter(Theater.is_active == True)
        return q.offset(skip).limit(limit).all()

    @staticmethod
    async def toggle_theater_status(catalog_db: Session, theater_id: int) -> Optional[Theater]:
        theater = catalog_db.query(Theater).filter(Theater.id == theater_id).first()
        if not theater:
            return None
        theater.is_active = not theater.is_active
        catalog_db.commit()
        catalog_db.refresh(theater)

        try:
            from app.kafka.producer import publish_event
            await publish_event(
                "theater.toggled",
                {"theater_id": theater.id, "is_active": theater.is_active},
                key=str(theater.id),
            )
        except Exception as e:
            logger.warning("No se pudo publicar theater.toggled: %s", e)

        return theater

    # ── Purchases y reportes (HTTP a booking-service, dueño de cinema_booking) ──

    @staticmethod
    async def get_purchases(
        skip: int = 0,
        limit: int = 20,
        movie_id: Optional[int] = None,
        user_id: Optional[int] = None,
        purchase_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if movie_id:
            params["movie_id"] = movie_id
        if user_id:
            params["user_id"] = user_id
        if purchase_status:
            params["status"] = purchase_status
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.BOOKING_SERVICE_URL}/api/v1/purchases/internal/admin/purchases",
                params=params,
                headers=_INTERNAL_HEADERS,
            )
        if resp.status_code != status.HTTP_200_OK:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Error al consultar compras")
        return resp.json()

    @staticmethod
    async def get_sales_report() -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.BOOKING_SERVICE_URL}/api/v1/purchases/internal/admin/reports/sales",
                headers=_INTERNAL_HEADERS,
            )
        if resp.status_code != status.HTTP_200_OK:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Error al consultar el reporte de ventas")
        return resp.json()

    @staticmethod
    async def get_report_by_movie() -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.BOOKING_SERVICE_URL}/api/v1/purchases/internal/admin/reports/by-movie",
                headers=_INTERNAL_HEADERS,
            )
        if resp.status_code != status.HTTP_200_OK:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Error al consultar el reporte por película")
        return resp.json()

    @staticmethod
    async def get_report_by_date(period: str = "daily") -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.BOOKING_SERVICE_URL}/api/v1/purchases/internal/admin/reports/by-date",
                params={"period": period},
                headers=_INTERNAL_HEADERS,
            )
        if resp.status_code != status.HTTP_200_OK:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Error al consultar el reporte por fecha")
        return resp.json()
