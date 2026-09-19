# app/models/user.py — DTO del perfil de cinema_users (sin password_hash)
#
# Antes de 2026-09-19 este módulo era un modelo SQLAlchemy mapeado directo a
# cinema_users.users. admin-service ya no tiene conexión propia a esa base
# (ver ARCHITECTURE.md, "Aislamiento de base de datos por servicio", caso 2)
# — ahora resuelve estos datos por HTTP a user-service y los envuelve en este
# mismo shape para no tocar el resto del código (routes.py, dependencies.py
# solo hacen atributo-acceso, les da igual si viene de un ORM o de un dict).
import enum
from datetime import datetime

from pydantic import BaseModel as PydanticModel


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"


class User(PydanticModel):
    id: int
    email: str
    phone: str
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN
