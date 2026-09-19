# app/core/database.py — cinema_admin, la única base propia de admin-service
#
# Dueño de: movies, theaters, theater_movies, movie_showtimes (mismos
# modelos SQLAlchemy de siempre — lo único que cambió es a qué base física
# apuntan). catalog-service mantiene su propia copia de lectura en
# cinema_catalog, sincronizada por eventos Kafka (ver ARCHITECTURE.md,
# "Aislamiento de base de datos por servicio", caso 1).
#
# cinema_users (caso 2) y cinema_booking (caso 3) se resuelven por HTTP a
# user-service/booking-service — sin conexión de BD aquí.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings
from app.models.base import Base

admin_engine = create_engine(
    settings.DATABASE_URL_ADMIN,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    echo=settings.DEBUG,
)
AdminSession = sessionmaker(autocommit=False, autoflush=False, bind=admin_engine)


def get_admin_db():
    db = AdminSession()
    try:
        yield db
    finally:
        db.close()


# Alias para compatibilidad con rutas de películas/teatros/showtimes que usan get_db
get_db = get_admin_db


def init_schema() -> None:
    """
    Crea el esquema de cinema_admin si no existe (movies, theaters,
    theater_movies, movie_showtimes) — este servicio nunca corrió
    create_all antes porque compartía el esquema ya creado por
    catalog-service. Idempotente: no hace nada si las tablas ya existen.
    """
    # Importa los modelos para que se registren en Base.metadata antes de crear
    from app.models import movie, theater  # noqa: F401
    Base.metadata.create_all(bind=admin_engine)
