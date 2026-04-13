# app/models/booking_base.py
# Base separada para los modelos de cinema_booking.
# Necesaria porque cinema_booking.movies es una tabla de referencia local
# con menos columnas que cinema_catalog.movies.
# SQLAlchemy exige una metadata separada para evitar conflictos de tabla.
from datetime import datetime
from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class BookingBase(DeclarativeBase):
    pass


class BookingBaseModel(BookingBase):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BookingTicketBaseModel(BookingBase):
    """Base para tickets en cinema_booking — la tabla tickets no tiene is_active."""
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
