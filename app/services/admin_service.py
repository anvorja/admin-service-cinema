# app/services/admin_service.py
#
# Cada método recibe la sesión de la DB que corresponde a su dominio:
#   • booking_db → cinema_booking (compras, tickets)
#   • catalog_db → cinema_catalog (teatro — heredado del método get_theaters)
#
# Los métodos de usuarios ya NO reciben sesión de BD: cinema_users es de
# user-service, se consulta por HTTP interno (ver ARCHITECTURE.md,
# "Aislamiento de base de datos por servicio", caso 2).
import logging
from typing import List, Optional, Dict, Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, case

from app.core.config import settings
from app.models.user import User
from app.models.purchase import Purchase, PurchaseStatus   # BookingBase — cinema_booking
from app.models.booking_refs import BookingMovieRef
from app.models.theater import Theater                     # CatalogBase — cinema_catalog

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

    # ── Theaters (cinema_catalog) ──────────────────────────────────────────────

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
    def toggle_theater_status(catalog_db: Session, theater_id: int) -> Optional[Theater]:
        theater = catalog_db.query(Theater).filter(Theater.id == theater_id).first()
        if not theater:
            return None
        theater.is_active = not theater.is_active
        catalog_db.commit()
        catalog_db.refresh(theater)
        return theater

    # ── Purchases (cinema_booking) ─────────────────────────────────────────────

    @staticmethod
    def get_purchases(
        booking_db: Session,
        skip: int = 0,
        limit: int = 20,
        movie_id: Optional[int] = None,
        user_id: Optional[int] = None,
        purchase_status: Optional[str] = None,
    ) -> List[Purchase]:
        q = booking_db.query(Purchase).options(
            joinedload(Purchase.movie),
            joinedload(Purchase.user),
            joinedload(Purchase.tickets),
        )
        if movie_id:
            q = q.filter(Purchase.movie_id == movie_id)
        if user_id:
            q = q.filter(Purchase.user_id == user_id)
        if purchase_status:
            q = q.filter(Purchase.status == purchase_status.upper())
        return q.order_by(Purchase.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_sales_report(booking_db: Session) -> Dict[str, Any]:
        total_purchases = booking_db.query(Purchase).filter(
            Purchase.status == PurchaseStatus.CONFIRMED
        ).count()

        total_revenue = booking_db.query(func.sum(Purchase.total_amount)).filter(
            Purchase.status == PurchaseStatus.CONFIRMED
        ).scalar() or 0

        total_tickets = booking_db.query(func.sum(Purchase.quantity)).filter(
            Purchase.status == PurchaseStatus.CONFIRMED
        ).scalar() or 0

        total_refunds = booking_db.query(Purchase).filter(
            Purchase.status == PurchaseStatus.REFUNDED
        ).count()

        total_refunded_amount = booking_db.query(func.sum(Purchase.total_amount)).filter(
            Purchase.status == PurchaseStatus.REFUNDED
        ).scalar() or 0

        total_cancelled = booking_db.query(Purchase).filter(
            Purchase.status == PurchaseStatus.CANCELLED
        ).count()

        avg = total_revenue / total_purchases if total_purchases > 0 else 0

        return {
            "total_purchases": total_purchases,
            "total_revenue": float(total_revenue),
            "total_tickets_sold": int(total_tickets),
            "average_purchase_amount": round(avg, 2),
            "total_refunds": total_refunds,
            "total_refunded_amount": float(total_refunded_amount),
            "total_cancelled": total_cancelled,
            "currency": "COP",
        }

    @staticmethod
    def get_report_by_movie(booking_db: Session) -> Dict[str, Any]:
        rows = (
            booking_db.query(
                BookingMovieRef.id.label("movie_id"),
                BookingMovieRef.title.label("movie_title"),
                func.count(Purchase.id).label("purchases_count"),
                func.sum(Purchase.quantity).label("tickets_sold"),
                func.sum(
                    case((Purchase.status == PurchaseStatus.CONFIRMED, Purchase.total_amount), else_=0)
                ).label("revenue"),
                func.sum(
                    case((Purchase.status == PurchaseStatus.REFUNDED, Purchase.total_amount), else_=0)
                ).label("refunded_amount"),
            )
            .join(BookingMovieRef, Purchase.movie_id == BookingMovieRef.id)
            .filter(Purchase.status.in_([PurchaseStatus.CONFIRMED, PurchaseStatus.REFUNDED]))
            .group_by(BookingMovieRef.id, BookingMovieRef.title)
            .order_by(
                func.sum(
                    case((Purchase.status == PurchaseStatus.CONFIRMED, Purchase.total_amount), else_=0)
                ).desc()
            )
            .all()
        )
        items = []
        for r in rows:
            revenue = float(r.revenue or 0)
            refunded = float(r.refunded_amount or 0)
            items.append({
                "movie_id": r.movie_id,
                "movie_title": r.movie_title,
                "purchases_count": r.purchases_count or 0,
                "tickets_sold": int(r.tickets_sold or 0),
                "revenue": revenue,
                "refunded_amount": refunded,
                "net_revenue": revenue - refunded,
            })
        return {"items": items, "currency": "COP"}

    @staticmethod
    def get_report_by_date(booking_db: Session, period: str = "daily") -> Dict[str, Any]:
        trunc_map = {"daily": "day", "weekly": "week", "monthly": "month"}
        trunc = trunc_map.get(period, "day")

        rows = (
            booking_db.query(
                func.date_trunc(trunc, Purchase.created_at).label("period"),
                func.count(Purchase.id).label("purchases_count"),
                func.sum(Purchase.quantity).label("tickets_sold"),
                func.sum(Purchase.total_amount).label("revenue"),
            )
            .filter(Purchase.status == PurchaseStatus.CONFIRMED)
            .group_by(func.date_trunc(trunc, Purchase.created_at))
            .order_by(func.date_trunc(trunc, Purchase.created_at))
            .all()
        )
        items = []
        for r in rows:
            items.append({
                "period": r.period.isoformat() if r.period else "",
                "purchases_count": r.purchases_count or 0,
                "tickets_sold": int(r.tickets_sold or 0),
                "revenue": float(r.revenue or 0),
            })
        return {"items": items, "period_type": period, "currency": "COP"}
