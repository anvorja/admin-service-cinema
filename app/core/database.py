# app/core/database.py — tres conexiones independientes para admin-service
#
#  ┌─────────────────────┬──────────────────┬──────────────────────────────┐
#  │ Session             │ DB               │ Tablas                       │
#  ├─────────────────────┼──────────────────┼──────────────────────────────┤
#  │ get_catalog_db      │ cinema_catalog   │ movies, theaters, showtimes  │
#  │ get_users_db        │ cinema_users     │ users (sin password_hash)    │
#  │ get_booking_db      │ cinema_booking   │ purchases, tickets           │
#  └─────────────────────┴──────────────────┴──────────────────────────────┘

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

_ENGINE_KWARGS = dict(
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=2,       # 3 pools × 2 = 6 conexiones base (era 5 → 15)
    max_overflow=3,    # 3 pools × 3 = 9 overflow máximo (era 10 → 30)
    pool_timeout=30,
)

# ── Catalog DB ─────────────────────────────────────────────────────────────────
catalog_engine = create_engine(settings.DATABASE_URL_CATALOG, echo=settings.DEBUG, **_ENGINE_KWARGS)
CatalogSession = sessionmaker(autocommit=False, autoflush=False, bind=catalog_engine)


def get_catalog_db():
    db = CatalogSession()
    try:
        yield db
    finally:
        db.close()


# Alias para compatibilidad con rutas de películas/salas que usan get_db
get_db = get_catalog_db

# ── Users DB ───────────────────────────────────────────────────────────────────
users_engine = create_engine(settings.DATABASE_URL_USERS, echo=settings.DEBUG, **_ENGINE_KWARGS)
UsersSession = sessionmaker(autocommit=False, autoflush=False, bind=users_engine)


def get_users_db():
    db = UsersSession()
    try:
        yield db
    finally:
        db.close()


# ── Booking DB ─────────────────────────────────────────────────────────────────
# Usa BookingBase (metadata separada) porque cinema_booking.movies tiene menos
# columnas que cinema_catalog.movies — no se pueden compartir modelos.
booking_engine = create_engine(settings.DATABASE_URL_BOOKING, echo=settings.DEBUG, **_ENGINE_KWARGS)
BookingSession = sessionmaker(autocommit=False, autoflush=False, bind=booking_engine)


def get_booking_db():
    db = BookingSession()
    try:
        yield db
    finally:
        db.close()
