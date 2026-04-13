# app/models/purchase.py — refleja cinema_booking
# Usa BookingBase (metadata separada) para evitar conflictos con
# cinema_catalog.movies que tiene más columnas.
import enum
from sqlalchemy import String, Integer, Float, ForeignKey, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional, Dict, Any

from .booking_base import BookingBaseModel, BookingTicketBaseModel
from .booking_refs import BookingUserRef, BookingMovieRef


class PurchaseStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class TicketStatus(str, enum.Enum):
    ACTIVE = "active"
    USED = "used"
    CANCELLED = "cancelled"


class Purchase(BookingBaseModel):
    __tablename__ = "purchases"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    movie_id: Mapped[int] = mapped_column(Integer, ForeignKey("movies.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus), default=PurchaseStatus.PENDING, nullable=False, index=True
    )

    user: Mapped[BookingUserRef] = relationship(foreign_keys=[user_id], lazy="joined")
    movie: Mapped[BookingMovieRef] = relationship(foreign_keys=[movie_id], lazy="joined")
    tickets: Mapped[List["Ticket"]] = relationship(back_populates="purchase", cascade="all, delete-orphan")

    @property
    def is_confirmed(self) -> bool:
        return self.status == PurchaseStatus.CONFIRMED


class Ticket(BookingTicketBaseModel):
    __tablename__ = "tickets"

    purchase_id: Mapped[int] = mapped_column(Integer, ForeignKey("purchases.id"), nullable=False, index=True)
    ticket_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    seat_number: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.ACTIVE, nullable=False, index=True
    )

    purchase: Mapped["Purchase"] = relationship(back_populates="tickets")
