# admin-service-cinema

Panel administrativo del sistema: gestión de películas, teatros, usuarios y reportes de ventas — solo accesible a usuarios `is_admin=true`.

## Responsabilidad

No tiene base de datos propia. Es intencional: en vez de duplicar datos u orquestar por HTTP, se conecta directamente a las tres bases de datos que necesita gestionar o consultar —`cinema_catalog`, `cinema_users` y `cinema_booking`— y opera sobre ellas con sus propios modelos SQLAlchemy. Gestiona el ciclo de vida de películas y funciones (`showtimes`), activa/desactiva teatros y usuarios, expone reportes de ventas, y firma subidas de imágenes a Cloudinary para el frontend admin.

## Stack

FastAPI + SQLAlchemy 2.0 (tres engines, uno por base de datos) + Redis (blacklist de tokens) + aiokafka. Firma de Cloudinary manual (HMAC-SHA1 sobre los parámetros, sin SDK — ver `app/api/routes.py::sign_cloudinary_upload`). Puerto `8007`.

## API

Todos los endpoints van bajo `/api/v1/admin` y requieren JWT de un usuario admin (`get_current_admin`, valida contra `cinema_users` y rechaza tokens en la blacklist de Redis).

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/cloudinary/sign` | Firma una subida directa a Cloudinary (poster de película) |
| POST | `/movies` | Crea película — publica `movie.created` |
| GET | `/movies` | Lista películas |
| GET | `/movies/{id}` | Detalle de película |
| PUT | `/movies/{id}` | Actualiza película — publica `movie.updated` |
| PATCH | `/movies/{id}/toggle` | Activa/desactiva película — publica `movie.deactivated` solo al desactivar |
| POST | `/movies/{id}/showtimes` | Crea funciones (showtimes) para una película |
| DELETE | `/movies/{id}/showtimes/{showtime_id}` | Elimina una función |
| POST | `/theaters` | Crea sala/teatro |
| GET | `/theaters` | Lista teatros |
| PATCH | `/theaters/{id}/toggle` | Activa/desactiva teatro |
| GET | `/users` | Lista usuarios |
| GET | `/users/{id}` | Detalle de usuario |
| PATCH | `/users/{id}/toggle` | Activa/desactiva usuario — publica `user.deactivated` solo al desactivar |
| GET | `/purchases` | Lista compras |
| GET | `/purchases/movie/{movie_id}` | Compras de una película |
| GET | `/purchases/user/{user_id}` | Compras de un usuario |
| GET | `/reports/sales` | Reporte general de ventas |
| GET | `/reports/by-movie` | Ventas agrupadas por película |
| GET | `/reports/by-date` | Ventas agrupadas por fecha |

## Eventos Kafka

Solo publica — no consume nada. Ver el contrato completo (payload, semántica) en `../kafka-schemas-cinema/event_contracts_operativos.md`.

| Topic | Cuándo |
|---|---|
| `movie.created` | Al crear una película |
| `movie.updated` | Al editar campos de una película |
| `movie.deactivated` | Al desactivar una película (no al reactivar) |
| `user.deactivated` | Al desactivar un usuario |

## Variables de entorno clave

| Variable | Para qué |
|---|---|
| `DATABASE_URL_CATALOG` | Conexión a `cinema_catalog` (películas, teatros, funciones) |
| `DATABASE_URL_USERS` | Conexión a `cinema_users` (perfiles, autenticación de admin) |
| `DATABASE_URL_BOOKING` | Conexión a `cinema_booking` (compras, para reportes) |
| `JWT_SECRET` / `JWT_ALGORITHM` | Validar el token del admin — debe coincidir con `auth-service` |
| `REDIS_URL` | Blacklist de tokens invalidados |
| `KAFKA_ENABLED` / `KAFKA_BOOTSTRAP_SERVERS` / `KAFKA_API_KEY` / `KAFKA_API_SECRET` | Publicación de eventos (Confluent Cloud) |
| `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` / `CLOUDINARY_UPLOAD_PRESET` | Firmar subidas de imágenes |
| `BACKEND_CORS_ORIGINS` | Orígenes permitidos (acepta lista JSON o CSV) |

Qué variable va en cuál entorno: `../IMPLEMENTATION-GUIDE.md` Fase 4.4.

## Dependencias

No tiene API interna hacia otros microservicios — su acoplamiento es a nivel de base de datos, no de red:

- Comparte `cinema_catalog` con `catalog-service` (mismo esquema de películas/teatros).
- Comparte `cinema_users` con `user-service` y `auth-service` (perfiles y autenticación).
- Comparte `cinema_booking` con `booking-service` (solo lectura para reportes).

Por eso sus eventos Kafka existen: son la forma en que `booking-service` (y otros) se enteran de cambios hechos aquí sin consultar estas bases directamente.

## Correr en local

Standalone:
```bash
cd admin-service-cinema
uvicorn app.main:app --reload --port 8007
```

Como parte del stack completo (recomendado — ver `../IMPLEMENTATION-GUIDE.md` Fase 5):
```bash
cd ../infra-cinema
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build admin-service
```
