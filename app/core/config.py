# app/core/config.py
from typing import Any, List
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Admin Service"
    VERSION: str = "1.0.0"

    # cinema_catalog — películas, salas, funciones
    DATABASE_URL: str
    # cinema_users — perfiles de usuario (sin password_hash)
    DATABASE_URL_USERS: str
    # cinema_booking — compras, tickets, reportes de ventas
    DATABASE_URL_BOOKING: str

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    REDIS_URL: str = ""

    # Kafka — publica user.deactivated cuando admin desactiva un usuario
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
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        if isinstance(v, list):
            return v
        raise ValueError(f"Invalid CORS origins: {v}")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
