# app/services/movie_service.py — write operations only (admin use case)
from typing import List, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_
from fastapi import HTTPException, status

from app.models.movie import Movie, MovieStatus
from app.models.theater import Theater, TheaterMovie, MovieShowtime, ShowtimeFormat
from app.schemas.admin import MovieCreate, MovieUpdate
from app.core.cache import cache


class MovieService:

    @staticmethod
    async def create_movie(db: Session, data: MovieCreate) -> Movie:
        existing = db.query(Movie).filter(Movie.title.ilike(data.title.strip())).first()
        if existing:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Película '{data.title}' ya existe",
            )

        movie = Movie(
            title=data.title.strip(),
            description=data.description.strip(),
            genre=data.genre.strip(),
            duration=data.duration,
            rating=data.rating.upper(),
            price=data.price,
            director=data.director.strip(),
            country=data.country.strip(),
            status=data.status,
            is_presale=data.is_presale,
            release_date=data.release_date,
            max_capacity=data.max_capacity,
            available_tickets=data.available_tickets,
            poster_url=str(data.poster_url),
            backdrop_url=str(data.backdrop_url),
            detail_1_url=str(data.detail_1_url),
            detail_2_url=str(data.detail_2_url),
        )
        db.add(movie)
        db.commit()
        db.refresh(movie)

        if data.theater_ids:
            MovieService._assign_theaters(db, movie.id, data.theater_ids)

        # Reload with relations so .theaters property works
        db.refresh(movie)
        cache.delete_pattern("home:*")

        # Publicar movie.created para que booking-service inserte la película en su tabla local
        try:
            from app.kafka.producer import publish_event
            await publish_event("movie.created", {
                "movie_id":          movie.id,
                "title":             movie.title,
                "genre":             movie.genre,
                "duration":          movie.duration,
                "rating":            movie.rating,
                "price":             float(movie.price),
                "available_tickets": movie.available_tickets,
                "max_capacity":      movie.max_capacity,
                "poster_url":        movie.poster_url,
            })
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("No se pudo publicar movie.created: %s", e)

        return movie

    @staticmethod
    def _assign_theaters(db: Session, movie_id: int, theater_ids: List[int]) -> None:
        for theater_id in theater_ids:
            exists = db.query(TheaterMovie).filter(
                TheaterMovie.theater_id == theater_id,
                TheaterMovie.movie_id == movie_id,
            ).first()
            if not exists:
                db.add(TheaterMovie(theater_id=theater_id, movie_id=movie_id))
        db.commit()

    @staticmethod
    def get_movies(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        include_inactive: bool = False,
        search: Optional[str] = None,
        genre: Optional[str] = None,
    ) -> List[Movie]:
        q = db.query(Movie).options(
            selectinload(Movie.theater_movies).selectinload(TheaterMovie.theater)
        )
        if not include_inactive:
            q = q.filter(Movie.is_active == True)
        if search:
            term = f"%{search.strip()}%"
            q = q.filter(or_(Movie.title.ilike(term), Movie.description.ilike(term)))
        if genre:
            q = q.filter(Movie.genre.ilike(f"%{genre.strip()}%"))
        return q.offset(skip).limit(limit).all()

    @staticmethod
    def get_movie_by_id(db: Session, movie_id: int, include_inactive: bool = False) -> Optional[Movie]:
        q = db.query(Movie).options(
            selectinload(Movie.theater_movies).selectinload(TheaterMovie.theater)
        ).filter(Movie.id == movie_id)
        if not include_inactive:
            q = q.filter(Movie.is_active == True)
        return q.first()

    @staticmethod
    async def update_movie(db: Session, movie_id: int, data: MovieUpdate) -> Optional[Movie]:
        movie = db.query(Movie).filter(Movie.id == movie_id).first()
        if not movie:
            return None

        # Campos que afectan a cinema_booking y necesitan sincronización
        _SYNC_FIELDS = {"price", "available_tickets", "max_capacity", "title", "genre", "duration", "rating", "poster_url"}
        changed: dict = {}

        for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            if not hasattr(movie, field):
                continue
            if isinstance(value, str) and not field.endswith("_url"):
                value = value.strip()
            if field == "rating" and value:
                value = value.upper()
            if field.endswith("_url"):
                value = str(value)
            setattr(movie, field, value)
            if field in _SYNC_FIELDS:
                changed[field] = value

        db.commit()
        db.refresh(movie)
        cache.delete_pattern("home:*")

        # Publicar movie.updated para que booking-service y catalog-service sincronicen
        if changed:
            try:
                from app.kafka.producer import publish_event
                await publish_event("movie.updated", {"movie_id": movie_id, **changed})
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("No se pudo publicar movie.updated: %s", e)

        return movie

    @staticmethod
    async def toggle_movie_status(db: Session, movie_id: int) -> Optional[Movie]:
        movie = db.query(Movie).filter(Movie.id == movie_id).first()
        if not movie:
            return None
        was_active = movie.is_active
        movie.is_active = not movie.is_active
        db.commit()
        db.refresh(movie)
        cache.delete_pattern("home:*")

        # Publicar movie.deactivated cuando se desactiva, para que booking-service
        # marque la película como inactiva en su tabla local y bloquee nuevas compras.
        if was_active and not movie.is_active:
            try:
                from app.kafka.producer import publish_event
                await publish_event("movie.deactivated", {"movie_id": movie_id})
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("No se pudo publicar movie.deactivated: %s", e)

        return movie

    @staticmethod
    def create_showtimes(
        db: Session,
        movie_id: int,
        start_date: date,
        days_count: int = 7,
        theater_ids: Optional[List[int]] = None,
    ) -> List[MovieShowtime]:
        movie = db.query(Movie).filter(Movie.id == movie_id).first()
        if not movie:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Película no encontrada")

        if not theater_ids:
            theater_ids = [tm.theater_id for tm in movie.theater_movies if tm.is_active]

        standard_times = [
            {"time": "12:30", "format": ShowtimeFormat.TWO_D_DUBBED},
            {"time": "15:20", "format": ShowtimeFormat.TWO_D_DUBBED},
            {"time": "18:10", "format": ShowtimeFormat.TWO_D_DUBBED},
            {"time": "21:00", "format": ShowtimeFormat.TWO_D_SUBTITLED},
        ]

        created = []
        for day_offset in range(days_count):
            show_date = start_date + timedelta(days=day_offset)
            for theater_id in theater_ids:
                for s in standard_times:
                    exists = db.query(MovieShowtime).filter(
                        MovieShowtime.movie_id == movie_id,
                        MovieShowtime.theater_id == theater_id,
                        MovieShowtime.show_date == show_date,
                        MovieShowtime.show_time == s["time"],
                        MovieShowtime.format == s["format"],
                    ).first()
                    if not exists:
                        showtime = MovieShowtime(
                            movie_id=movie_id,
                            theater_id=theater_id,
                            show_date=show_date,
                            show_time=s["time"],
                            format=s["format"],
                        )
                        db.add(showtime)
                        created.append(showtime)

        db.commit()
        for st in created:
            db.refresh(st)
        return created
