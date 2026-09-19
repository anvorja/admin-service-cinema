# app/core/database.py — última conexión propia de admin-service
#
#  ┌─────────────────────┬──────────────────┬──────────────────────────────┐
#  │ Session             │ DB               │ Tablas                       │
#  ├─────────────────────┼──────────────────┼──────────────────────────────┤
#  │ get_catalog_db      │ cinema_catalog   │ movies, theaters, showtimes  │
#  └─────────────────────┴──────────────────┴──────────────────────────────┘
#
# cinema_users (caso 2) y cinema_booking (caso 3) ya no tienen conexión
# propia aquí — se resuelven por HTTP a user-service/booking-service (ver
# ARCHITECTURE.md, "Aislamiento de base de datos por servicio"). Queda
# cinema_catalog, compartida con catalog-service (caso 1, pendiente).

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

_ENGINE_KWARGS = dict(
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
)

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
