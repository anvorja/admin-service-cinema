# app/core/config.py
from typing import Any, List
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Admin Service"
    VERSION: str = "1.0.0"

    # cinema_admin — dueño exclusivo: movies, theaters, theater_movies,
    # movie_showtimes (el "lado de escritura"/comando de este dominio).
    # Hasta 2026-09-19 esto vivía en cinema_catalog, compartida físicamente
    # con catalog-service; ver ARCHITECTURE.md, "Aislamiento de base de
    # datos por servicio", caso 1. catalog-service mantiene su propia copia
    # de lectura en cinema_catalog, sincronizada vía eventos Kafka
    # (movie.*, theater.*, showtime.*) — nunca por DB compartida.
    DATABASE_URL_ADMIN: str

    # user-service y booking-service son dueños de cinema_users y
    # cinema_booking respectivamente — se resuelven vía HTTP interno (casos
    # 2 y 3 de la misma decisión).
    USER_SERVICE_URL: str = "http://user-service:8008"
    BOOKING_SERVICE_URL: str = "http://booking-service:8004"
    # Secreto compartido para llamar a rutas /internal/* de user-service y
    # booking-service. Debe coincidir con INTERNAL_SERVICE_TOKEN allá.
    INTERNAL_SERVICE_TOKEN: str = ""

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    REDIS_URL: str = ""

    # Kafka — publica movie.*/theater.*/showtime.* para que catalog-service
    # sincronice su copia de lectura (caso 1). user.deactivated ya no lo
    # publica este servicio (lo publica user-service, ver caso 2).
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = ""
    KAFKA_API_KEY: str = ""
    KAFKA_API_SECRET: str = ""

    # Cloudinary — for signed upload URLs
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_UPLOAD_PRESET: str = "cinema"

    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:8090",
        "http://localhost:5173",
    ]
    DEBUG: bool = False

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                import json
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in stripped.split(",") if i.strip()]
        raise ValueError(f"Invalid CORS origins: {v}")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
