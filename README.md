# admin-service-cinema

Panel administrativo del sistema: gestión de películas, teatros, usuarios y reportes de ventas — solo accesible a usuarios `is_admin=true`.

## Responsabilidad

No tiene base de datos propia. Gestiona el ciclo de vida de películas y funciones (`showtimes`), activa/desactiva teatros y usuarios, expone reportes de ventas, y firma subidas de imágenes a Cloudinary para el frontend admin.

Hasta 2026-09-19 resolvía todo (incluyendo auth/autorización del propio panel) conectándose directo a `cinema_catalog`, `cinema_users` y `cinema_booking` con sus propios modelos SQLAlchemy. Desde esa fecha, **`cinema_users` y `cinema_booking` ya no tienen conexión directa** — se resuelven por HTTP interno a `user-service` y `booking-service` respectivamente (dueños reales de cada base), con una caché corta en Redis para el perfil de usuario. Solo `cinema_catalog` sigue siendo acceso directo (caso 1, pendiente — ver `../ARCHITECTURE.md`, "Aislamiento de base de datos por servicio").

## Stack

FastAPI + SQLAlchemy 2.0 (un engine propio: `cinema_catalog`) + `httpx` (llamadas a `user-service` y `booking-service`) + Redis (blacklist de tokens + caché de perfiles) + aiokafka. Firma de Cloudinary manual (HMAC-SHA1 sobre los parámetros, sin SDK — ver `app/api/routes.py::sign_cloudinary_upload`). Puerto `8007`.

## API

Todos los endpoints van bajo `/api/v1/admin` y requieren JWT de un usuario admin (`get_current_admin`, que resuelve el usuario contra `user-service` — ver Dependencias — y rechaza tokens en la blacklist de Redis).

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
| GET | `/users` | Lista usuarios (vía HTTP a `user-service`) |
| GET | `/users/{id}` | Detalle de usuario (vía HTTP a `user-service`) |
| PATCH | `/users/{id}/toggle` | Activa/desactiva usuario — la aplica `user-service` (publica `user.deactivated` solo al desactivar); aquí solo se valida que un admin no pueda desactivarse a sí mismo |
| GET | `/purchases` | Lista compras (vía HTTP a `booking-service`) |
| GET | `/purchases/movie/{movie_id}` | Compras de una película (vía HTTP a `booking-service`) |
| GET | `/purchases/user/{user_id}` | Compras de un usuario (vía HTTP a `booking-service`) |
| GET | `/reports/sales` | Reporte general de ventas (vía HTTP a `booking-service`) |
| GET | `/reports/by-movie` | Ventas agrupadas por película (vía HTTP a `booking-service`) |
| GET | `/reports/by-date` | Ventas agrupadas por fecha (vía HTTP a `booking-service`) |

## Eventos Kafka

Solo publica — no consume nada. Ver el contrato completo (payload, semántica) en `../kafka-schemas-cinema/event_contracts_operativos.md`. `user.deactivated` ya no lo publica este servicio — desde el caso 2 lo publica `user-service`, que es quien aplica el cambio.

| Topic | Cuándo |
|---|---|
| `movie.created` | Al crear una película |
| `movie.updated` | Al editar campos de una película |
| `movie.deactivated` | Al desactivar una película (no al reactivar) |

## Variables de entorno clave

| Variable | Para qué |
|---|---|
| `DATABASE_URL_CATALOG` | Conexión a `cinema_catalog` (películas, teatros, funciones) |
| `USER_SERVICE_URL` | URL de `user-service` — resuelve auth/autorización del panel y el CRUD de usuarios (default local: `http://user-service:8008`) |
| `BOOKING_SERVICE_URL` | URL de `booking-service` — compras y reportes de ventas (default local: `http://booking-service:8004`) |
| `INTERNAL_SERVICE_TOKEN` | Header `X-Internal-Token` en las llamadas a `user-service`/`booking-service` — debe coincidir con el mismo valor allá |
| `JWT_SECRET` / `JWT_ALGORITHM` | Validar el token del admin — debe coincidir con `auth-service` |
| `REDIS_URL` | Blacklist de tokens invalidados + caché corta (60s) de perfiles resueltos desde `user-service` |
| `KAFKA_ENABLED` / `KAFKA_BOOTSTRAP_SERVERS` / `KAFKA_API_KEY` / `KAFKA_API_SECRET` | Publicación de eventos (Confluent Cloud) |
| `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` / `CLOUDINARY_UPLOAD_PRESET` | Firmar subidas de imágenes |
| `BACKEND_CORS_ORIGINS` | Orígenes permitidos (acepta lista JSON o CSV) |

Qué variable va en cuál entorno: `../IMPLEMENTATION-GUIDE.md` Fase 4.4.

## Dependencias

- **HTTP** → `user-service` (`/api/v1/users/internal/*`, protegido por `X-Internal-Token`): resuelve auth/autorización del panel (`get_current_admin`) y el CRUD de `/admin/users`. Desde 2026-09-19 — antes era una conexión directa a `cinema_users` (ver `../ARCHITECTURE.md`, "Aislamiento de base de datos por servicio", caso 2).
- **HTTP** → `booking-service` (`/api/v1/purchases/internal/admin/*`, protegido por `X-Internal-Token`): `/purchases*` y `/reports/*`. Desde 2026-09-19 — antes era una conexión directa a `cinema_booking` (caso 3 de la misma decisión).
- **Base de datos compartida** (pendiente de resolver — caso 1, el único que queda):
  - Comparte `cinema_catalog` con `catalog-service` (mismo esquema de películas/teatros).
- Sus eventos Kafka de películas (`movie.*`) son la forma en que `catalog-service`/`booking-service` se enteran de cambios hechos aquí sin consultar `cinema_catalog` directamente — aunque hoy `catalog-service` no los consume todavía (ver `HALLAZGOS.md`).

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
