# app/schemas/admin.py
import hashlib
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime, date
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────────

class MovieStatus(str, Enum):
    IN_THEATERS = "in_theaters"
    COMING_SOON = "coming_soon"
    ENDED = "ended"


class ShowtimeFormat(str, Enum):
    TWO_D_DUBBED = "2d_dubbed"
    TWO_D_SUBTITLED = "2d_subtitled"
    THREE_D = "3d"
    IMAX = "imax"


# ── Movie schemas ──────────────────────────────────────────────────────────────

class MovieCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10, max_length=1000)
    genre: str = Field(..., min_length=1, max_length=50)
    duration: int = Field(..., gt=0, le=600)
    rating: str = Field(..., pattern="^(G|PG|PG-13|R|NC-17)$")
    price: float = Field(..., gt=0, le=100000)
    director: str = Field(..., max_length=200)
    country: str = Field(..., max_length=100)
    status: MovieStatus = MovieStatus.IN_THEATERS
    is_presale: bool = False
    release_date: date
    max_capacity: int = Field(default=100, ge=1, le=500)
    available_tickets: int = Field(default=100, ge=0, le=500)
    poster_url: HttpUrl
    backdrop_url: HttpUrl
    detail_1_url: HttpUrl
    detail_2_url: HttpUrl
    theater_ids: Optional[List[int]] = None


class MovieUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=10, max_length=1000)
    genre: Optional[str] = Field(None, min_length=1, max_length=50)
    duration: Optional[int] = Field(None, gt=0, le=600)
    rating: Optional[str] = Field(None, pattern="^(G|PG|PG-13|R|NC-17)$")
    price: Optional[float] = Field(None, gt=0, le=100000)
    director: Optional[str] = Field(None, max_length=200)
    country: Optional[str] = Field(None, max_length=100)
    status: Optional[MovieStatus] = None
    is_presale: Optional[bool] = None
    release_date: Optional[date] = None
    max_capacity: Optional[int] = Field(None, ge=1, le=500)
    available_tickets: Optional[int] = Field(None, ge=0, le=500)
    poster_url: Optional[HttpUrl] = None
    backdrop_url: Optional[HttpUrl] = None
    detail_1_url: Optional[HttpUrl] = None
    detail_2_url: Optional[HttpUrl] = None


class MovieResponse(BaseModel):
    id: int
    title: str
    description: str
    genre: str
    duration: int
    rating: str
    price: float
    director: str
    country: str
    status: str
    is_presale: bool
    release_date: date
    formatted_release_date: str
    max_capacity: int
    available_tickets: int
    sold_tickets: int
    occupancy_rate: float
    is_active: bool
    created_at: datetime
    poster_url: str
    backdrop_url: str
    detail_1_url: str
    detail_2_url: str
    theaters: List[str]
    is_available: bool
    is_in_theaters: bool
    is_coming_soon: bool

    @classmethod
    def from_orm(cls, m):
        return cls(
            id=m.id, title=m.title, description=m.description, genre=m.genre,
            duration=m.duration, rating=m.rating, price=m.price,
            director=m.director, country=m.country, status=m.status.value,
            is_presale=m.is_presale, release_date=m.release_date,
            formatted_release_date=m.formatted_release_date,
            max_capacity=m.max_capacity, available_tickets=m.available_tickets,
            sold_tickets=m.sold_tickets, occupancy_rate=m.occupancy_rate,
            is_active=m.is_active, created_at=m.created_at,
            poster_url=m.poster_url, backdrop_url=m.backdrop_url,
            detail_1_url=m.detail_1_url, detail_2_url=m.detail_2_url,
            theaters=m.theaters, is_available=m.is_available,
            is_in_theaters=m.is_in_theaters, is_coming_soon=m.is_coming_soon,
        )


# ── Theater schemas ────────────────────────────────────────────────────────────

class TheaterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)


class TheaterResponse(BaseModel):
    id: int
    name: str
    location: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    @classmethod
    def from_orm(cls, t):
        return cls(
            id=t.id, name=t.name, location=t.location,
            description=t.description, is_active=t.is_active, created_at=t.created_at,
        )


# ── Showtime schemas ───────────────────────────────────────────────────────────

class CreateShowtimesRequest(BaseModel):
    start_date: date
    days_count: int = Field(default=30, ge=1, le=120)
    theater_ids: Optional[List[int]] = None
    hall_number: Optional[int] = Field(default=None, ge=1, description="Número de sala física (1, 2, 3…)")
    hall_template_id: Optional[int] = Field(default=None, description="ID del layout de asientos a usar")


class ShowtimeResponse(BaseModel):
    id: int
    show_date: date
    show_time: str
    format: str
    capacity: int
    available_tickets: int
    theater_name: str
    hall_number: Optional[int] = None
    hall_template_id: Optional[int] = None

    @classmethod
    def from_orm(cls, s):
        return cls(
            id=s.id, show_date=s.show_date, show_time=s.show_time,
            format=s.format.value, capacity=s.capacity,
            available_tickets=s.available_tickets, theater_name=s.theater.name,
            hall_number=s.hall_number, hall_template_id=s.hall_template_id,
        )


# ── User schemas ───────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    email: str
    phone: str
    first_name: str
    last_name: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    @classmethod
    def from_orm(cls, u):
        return cls(
            id=u.id, email=u.email, phone=u.phone,
            first_name=u.first_name, last_name=u.last_name,
            full_name=u.full_name, role=u.role.value,
            is_active=u.is_active, created_at=u.created_at,
        )


# ── Purchase schemas ───────────────────────────────────────────────────────────

class TicketResponse(BaseModel):
    id: int
    ticket_code: str
    seat_number: str
    status: str
    created_at: datetime

    @classmethod
    def from_orm(cls, t):
        return cls(
            id=t.id, ticket_code=t.ticket_code, seat_number=t.seat_number,
            status=t.status.value, created_at=t.created_at,
        )


class PurchaseUserInfo(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str


class PurchaseMovieInfo(BaseModel):
    id: int
    title: str
    genre: str


class PurchaseResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    movie_title: str
    user_full_name: str
    user: PurchaseUserInfo
    movie: PurchaseMovieInfo
    quantity: int
    total_amount: float
    status: str
    is_confirmed: bool
    created_at: datetime
    tickets: List[TicketResponse]
    payment_summary: Dict[str, Any]

    @classmethod
    def from_orm(cls, p):
        return cls(
            id=p.id, user_id=p.user_id, movie_id=p.movie_id,
            movie_title=p.movie.title, user_full_name=p.user.full_name,
            user=PurchaseUserInfo(
                id=p.user.id,
                first_name=p.user.first_name,
                last_name=p.user.last_name,
                email=p.user.email,
            ),
            movie=PurchaseMovieInfo(
                id=p.movie.id,
                title=p.movie.title,
                genre=p.movie.genre,
            ),
            quantity=p.quantity, total_amount=p.total_amount,
            status=p.status.value, is_confirmed=p.is_confirmed,
            created_at=p.created_at,
            tickets=[TicketResponse.from_orm(t) for t in p.tickets],
            payment_summary={
                "last_four": p.payment_info.get("last_four", "****") if p.payment_info else "****",
                "total_amount": p.total_amount,
                "currency": "COP",
            },
        )


class SalesReport(BaseModel):
    total_purchases: int
    total_revenue: float
    total_tickets_sold: int
    average_purchase_amount: float
    total_refunds: int
    total_refunded_amount: float
    total_cancelled: int
    currency: str


class MovieSalesItem(BaseModel):
    movie_id: int
    movie_title: str
    purchases_count: int
    tickets_sold: int
    revenue: float
    refunded_amount: float
    net_revenue: float


class MovieSalesReport(BaseModel):
    items: List[MovieSalesItem]
    currency: str


class DateSalesItem(BaseModel):
    period: str
    purchases_count: int
    tickets_sold: int
    revenue: float


class DateSalesReport(BaseModel):
    items: List[DateSalesItem]
    period_type: str
    currency: str


# ── Cloudinary schema ──────────────────────────────────────────────────────────

class CloudinarySignRequest(BaseModel):
    public_id: str
    folder: str = "cinema/movies"


class CloudinarySignResponse(BaseModel):
    signature: str
    timestamp: int
    api_key: str
    upload_preset: str
