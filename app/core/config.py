# app/core/config.py
from typing import Any, List
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Admin Service"
    VERSION: str = "1.0.0"

    # cinema_catalog — películas, salas, funciones
    DATABASE_URL_CATALOG: str
    # cinema_booking — compras, tickets, reportes de ventas
    DATABASE_URL_BOOKING: str

    # user-service — dueño de cinema_users. Desde 2026-09-19 admin-service ya
    # no conecta directo a esa base (ver ARCHITECTURE.md, "Aislamiento de
    # base de datos por servicio", caso 2); resuelve auth/autorización y el
    # panel de usuarios vía HTTP interno.
    USER_SERVICE_URL: str = "http://user-service:8008"
    # Secreto compartido para llamar a rutas /internal/* de user-service.
    # Debe coincidir con INTERNAL_SERVICE_TOKEN en user-service-cinema.
    INTERNAL_SERVICE_TOKEN: str = ""

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    REDIS_URL: str = ""

    # Kafka — hoy sin uso directo (user.deactivated ahora lo publica
    # user-service, ver caso 2 arriba); queda por si se necesita a futuro.
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
