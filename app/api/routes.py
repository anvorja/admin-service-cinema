# app/api/routes.py
import hashlib
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, get_users_db, get_booking_db
from app.api.dependencies import get_current_admin
from app.models.user import User
from app.models.theater import Theater
from app.schemas.admin import (
    MovieCreate, MovieUpdate, MovieResponse,
    TheaterCreate, TheaterResponse,
    CreateShowtimesRequest, ShowtimeResponse,
    UserResponse,
    PurchaseResponse, SalesReport,
    CloudinarySignRequest, CloudinarySignResponse,
)
from app.services.movie_service import MovieService
from app.services.admin_service import AdminService

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# ── Cloudinary ─────────────────────────────────────────────────────────────────

@router.post("/cloudinary/sign", response_model=CloudinarySignResponse)
async def sign_cloudinary_upload(
    body: CloudinarySignRequest,
    _: User = Depends(get_current_admin),
):
    if not settings.CLOUDINARY_API_SECRET:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Cloudinary no configurado")

    timestamp = int(time.time())
    params = {
        "folder": body.folder,
        "public_id": body.public_id,
        "timestamp": str(timestamp),
        "upload_preset": settings.CLOUDINARY_UPLOAD_PRESET,
    }
    params_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    signature = hashlib.sha1((params_string + settings.CLOUDINARY_API_SECRET).encode()).hexdigest()

    return CloudinarySignResponse(
        signature=signature,
        timestamp=timestamp,
        api_key=settings.CLOUDINARY_API_KEY,
        upload_preset=settings.CLOUDINARY_UPLOAD_PRESET,
    )


# ── Movies (cinema_catalog) ────────────────────────────────────────────────────

@router.post("/movies", response_model=MovieResponse, status_code=status.HTTP_201_CREATED)
async def create_movie(
    data: MovieCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    movie = MovieService.create_movie(db, data)
    return MovieResponse.from_orm(movie)


@router.get("/movies", response_model=List[MovieResponse])
async def list_movies(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False),
    search: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    movies = MovieService.get_movies(db, skip, limit, include_inactive, search, genre)
    return [MovieResponse.from_orm(m) for m in movies]


@router.get("/movies/{movie_id}", response_model=MovieResponse)
async def get_movie(
    movie_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    movie = MovieService.get_movie_by_id(db, movie_id, include_inactive=True)
    if not movie:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Película no encontrada")
    return MovieResponse.from_orm(movie)


@router.put("/movies/{movie_id}", response_model=MovieResponse)
async def update_movie(
    movie_id: int,
    data: MovieUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    movie = await MovieService.update_movie(db, movie_id, data)
    if not movie:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Película no encontrada")
    return MovieResponse.from_orm(movie)


@router.patch("/movies/{movie_id}/toggle", response_model=MovieResponse)
async def toggle_movie(
    movie_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    movie = MovieService.toggle_movie_status(db, movie_id)
    if not movie:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Película no encontrada")
    return MovieResponse.from_orm(movie)


@router.post("/movies/{movie_id}/showtimes", response_model=List[ShowtimeResponse])
async def create_showtimes(
    movie_id: int,
    data: CreateShowtimesRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    showtimes = MovieService.create_showtimes(
        db, movie_id, data.start_date, data.days_count, data.theater_ids
    )
    return [ShowtimeResponse.from_orm(s) for s in showtimes]


# ── Theaters (cinema_catalog) ──────────────────────────────────────────────────

@router.post("/theaters", response_model=TheaterResponse, status_code=status.HTTP_201_CREATED)
async def create_theater(
    data: TheaterCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    existing = db.query(Theater).filter(Theater.name == data.name).first()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Teatro '{data.name}' ya existe")

    theater = Theater(name=data.name, location=data.location, description=data.description)
    db.add(theater)
    db.commit()
    db.refresh(theater)
    return TheaterResponse.from_orm(theater)


@router.get("/theaters", response_model=List[TheaterResponse])
async def list_theaters(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    theaters = AdminService.get_theaters(db, skip, limit, include_inactive)
    return [TheaterResponse.from_orm(t) for t in theaters]


@router.patch("/theaters/{theater_id}/toggle", response_model=TheaterResponse)
async def toggle_theater(
    theater_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Activar / desactivar un teatro."""
    theater = AdminService.toggle_theater_status(db, theater_id)
    if not theater:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Teatro no encontrado")
    return TheaterResponse.from_orm(theater)


# ── Users (cinema_users) ───────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False),
    search: Optional[str] = Query(None),
    users_db: Session = Depends(get_users_db),
    _: User = Depends(get_current_admin),
):
    users = AdminService.get_users(users_db, skip, limit, include_inactive, search)
    return [UserResponse.from_orm(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    users_db: Session = Depends(get_users_db),
    _: User = Depends(get_current_admin),
):
    user = AdminService.get_user_by_id(users_db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return UserResponse.from_orm(user)


@router.patch("/users/{user_id}/toggle", response_model=UserResponse)
async def toggle_user(
    user_id: int,
    users_db: Session = Depends(get_users_db),
    current_admin: User = Depends(get_current_admin),
):
    user = await AdminService.toggle_user_status(users_db, user_id, current_admin.id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return UserResponse.from_orm(user)


# ── Purchases (cinema_booking) ─────────────────────────────────────────────────

@router.get("/purchases", response_model=List[PurchaseResponse])
async def list_purchases(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    movie_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    purchase_status: Optional[str] = Query(None, alias="status"),
    booking_db: Session = Depends(get_booking_db),
    _: User = Depends(get_current_admin),
):
    purchases = AdminService.get_purchases(booking_db, skip, limit, movie_id, user_id, purchase_status)
    return [PurchaseResponse.from_orm(p) for p in purchases]


@router.get("/purchases/movie/{movie_id}", response_model=List[PurchaseResponse])
async def purchases_by_movie(
    movie_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    booking_db: Session = Depends(get_booking_db),
    _: User = Depends(get_current_admin),
):
    purchases = AdminService.get_purchases(booking_db, skip, limit, movie_id=movie_id)
    return [PurchaseResponse.from_orm(p) for p in purchases]


@router.get("/purchases/user/{user_id}", response_model=List[PurchaseResponse])
async def purchases_by_user(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    booking_db: Session = Depends(get_booking_db),
    _: User = Depends(get_current_admin),
):
    purchases = AdminService.get_purchases(booking_db, skip, limit, user_id=user_id)
    return [PurchaseResponse.from_orm(p) for p in purchases]


@router.get("/reports/sales", response_model=SalesReport)
async def sales_report(
    booking_db: Session = Depends(get_booking_db),
    _: User = Depends(get_current_admin),
):
    return AdminService.get_sales_report(booking_db)
