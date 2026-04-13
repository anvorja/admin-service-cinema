# app/models/booking_refs.py
# Modelos ligeros que reflejan las tablas de referencia local en cinema_booking.
# Solo contienen las columnas que existen en esa DB (subconjunto del catálogo).
#
# Nota: cinema_booking.users.role es VARCHAR(20), no un tipo enum nativo de
# PostgreSQL — se mapea como String para evitar conflictos de tipo DDL.
from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column

from .booking_base import BookingBaseModel


class BookingUserRef(BookingBaseModel):
    """Refleja cinema_booking.users (tabla de referencia local, sin password_hash)."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="customer", nullable=False)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class BookingMovieRef(BookingBaseModel):
    """Refleja cinema_booking.movies (tabla de referencia local, solo columnas básicas)."""
    __tablename__ = "movies"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[str] = mapped_column(String(10), nullable=False)
    available_tickets: Mapped[int] = mapped_column(Integer, nullable=False)
    max_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
