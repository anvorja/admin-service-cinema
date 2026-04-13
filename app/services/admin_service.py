# app/services/admin_service.py
#
# Cada método recibe la sesión de la DB que corresponde a su dominio:
#   • users_db  → cinema_users   (perfiles, sin password_hash)
#   • booking_db → cinema_booking (compras, tickets)
#   • catalog_db → cinema_catalog (teatro — heredado del método get_theaters)
#
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_

from app.models.user import User
from app.models.purchase import Purchase, PurchaseStatus   # BookingBase — cinema_booking
from app.models.theater import Theater                     # CatalogBase — cinema_catalog


class AdminService:

    # ── Users (cinema_users) ───────────────────────────────────────────────────

    @staticmethod
    def get_users(
        users_db: Session,
        skip: int = 0,
        limit: int = 20,
        include_inactive: bool = False,
        search: Optional[str] = None,
    ) -> List[User]:
        q = users_db.query(User)
        if not include_inactive:
            q = q.filter(User.is_active == True)
        if search:
            term = f"%{search.strip()}%"
            q = q.filter(
                or_(
                    User.email.ilike(term),
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                )
            )
        return q.offset(skip).limit(limit).all()

    @staticmethod
    def get_user_by_id(users_db: Session, user_id: int) -> Optional[User]:
        return users_db.query(User).filter(User.id == user_id).first()

    @staticmethod
    async def toggle_user_status(users_db: Session, user_id: int, admin_id: int) -> Optional[User]:
        """
        Activa / desactiva un usuario en cinema_users.
        Si se desactiva, publica user.deactivated → auth-service invalida acceso en cinema_auth.
        """
        import logging
        logger = logging.getLogger(__name__)

        user = users_db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        if user.id == admin_id:
            from fastapi import HTTPException, status
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "No puedes deshabilitar tu propia cuenta"
            )
        was_active = user.is_active
        user.is_active = not user.is_active
        users_db.commit()
        users_db.refresh(user)

        # Si se desactivó, notificar a auth-service vía Kafka
        if was_active and not user.is_active:
            try:
                from app.kafka.producer import publish_event
                await publish_event("user.deactivated", {"user_id": user_id})
            except Exception as e:
                logger.warning("Could not publish user.deactivated: %s", e)

        return user

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

        avg = total_revenue / total_purchases if total_purchases > 0 else 0

        return {
            "total_purchases": total_purchases,
            "total_revenue": float(total_revenue),
            "total_tickets_sold": int(total_tickets),
            "average_purchase_amount": round(avg, 2),
            "currency": "COP",
        }
