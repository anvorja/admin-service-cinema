# app/models/theater.py
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime, date
import enum
from sqlalchemy import String, Integer, ForeignKey, Index, Date, Enum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .movie import Movie


class ShowtimeFormat(str, enum.Enum):
    TWO_D_DUBBED = "2d_dubbed"
    TWO_D_SUBTITLED = "2d_subtitled"
    THREE_D = "3d"
    IMAX = "imax"


class Theater(BaseModel):
    __tablename__ = "theaters"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)

    theater_movies: Mapped[List["TheaterMovie"]] = relationship(
        back_populates="theater", cascade="all, delete-orphan"
    )
    showtimes: Mapped[List["MovieShowtime"]] = relationship(
        back_populates="theater", cascade="all, delete-orphan"
    )


class TheaterMovie(BaseModel):
    __tablename__ = "theater_movies"

    theater_id: Mapped[int] = mapped_column(Integer, ForeignKey("theaters.id"), nullable=False, index=True)
    movie_id: Mapped[int] = mapped_column(Integer, ForeignKey("movies.id"), nullable=False, index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    available_tickets: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    theater: Mapped["Theater"] = relationship(back_populates="theater_movies")
    movie: Mapped["Movie"] = relationship(back_populates="theater_movies")

    __table_args__ = (Index("ix_theater_movie", "theater_id", "movie_id", unique=True),)


class MovieShowtime(BaseModel):
    __tablename__ = "movie_showtimes"

    movie_id: Mapped[int] = mapped_column(Integer, ForeignKey("movies.id"), nullable=False, index=True)
    theater_id: Mapped[int] = mapped_column(Integer, ForeignKey("theaters.id"), nullable=False, index=True)
    show_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    show_time: Mapped[str] = mapped_column(String(10), nullable=False)
    format: Mapped[ShowtimeFormat] = mapped_column(Enum(ShowtimeFormat), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    available_tickets: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    hall_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hall_template_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    movie: Mapped["Movie"] = relationship(back_populates="showtimes")
    theater: Mapped["Theater"] = relationship(back_populates="showtimes")

    __table_args__ = (
        Index("ix_showtime_unique", "movie_id", "theater_id", "show_date", "show_time", "format", unique=True),
        Index(
            "ix_showtime_hall_unique",
            "theater_id", "hall_number", "show_date", "show_time",
            unique=True,
            postgresql_where=text("hall_number IS NOT NULL"),
        ),
    )

    @property
    def datetime_show(self) -> datetime:
        hour, minute = map(int, self.show_time.split(":"))
        return datetime.combine(self.show_date, datetime.min.time().replace(hour=hour, minute=minute))
