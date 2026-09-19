# app/core/database.py — dos conexiones independientes para admin-service
#
#  ┌─────────────────────┬──────────────────┬──────────────────────────────┐
#  │ Session             │ DB               │ Tablas                       │
#  ├─────────────────────┼──────────────────┼──────────────────────────────┤
#  │ get_catalog_db      │ cinema_catalog   │ movies, theaters, showtimes  │
#  │ get_booking_db      │ cinema_booking   │ purchases, tickets           │
#  └─────────────────────┴──────────────────┴──────────────────────────────┘
#
# cinema_users ya no tiene conexión propia aquí — desde 2026-09-19 se
# resuelve por HTTP a user-service (ver ARCHITECTURE.md, "Aislamiento de
# base de datos por servicio", caso 2).

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

_ENGINE_KWARGS = dict(
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=3,       # 2 pools × 3 = 6 conexiones base
    max_overflow=5,    # 2 pools × 5 = 10 overflow máximo
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
