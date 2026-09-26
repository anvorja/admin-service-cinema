# admin-service-cinema

Panel administrativo del sistema: gestión de películas, teatros, usuarios y reportes de ventas — solo accesible a usuarios `is_admin=true`.

## Responsabilidad

Dueño exclusivo de `cinema_admin` (`movies`, `theaters`, `theater_movies`, `movie_showtimes`). Gestiona el ciclo de vida de películas y funciones (`showtimes`), activa/desactiva teatros y usuarios, expone reportes de ventas, y firma subidas de imágenes a Cloudinary para el frontend admin.

Hasta 2026-09-19 resolvía todo (incluyendo auth/autorización del propio panel) conectándose directo a `cinema_catalog`, `cinema_users` y `cinema_booking` — las tres compartidas con otros servicios, con sus propios modelos SQLAlchemy. Desde esa fecha, **ninguna de las tres tiene conexión directa**: `cinema_users` y `cinema_booking` se resuelven por HTTP interno a `user-service`/`booking-service`, y `cinema_catalog` se reemplazó por `cinema_admin` — una base propia, con el mismo esquema de siempre, que `catalog-service` sincroniza a su copia de lectura vía Kafka (`movie.*`/`theater.*`/`showtime.*`). Ver `../ARCHITECTURE.md`, "Aislamiento de base de datos por servicio", casos 1-3.

## Stack

FastAPI + SQLAlchemy 2.0 (un engine propio: `cinema_admin`) + `httpx` (llamadas a `user-service` y `booking-service`) + Redis (blacklist de tokens + caché de perfiles) + aiokafka (publica `movie.*`/`theater.*`/`showtime.*`, ver Eventos Kafka). Firma de Cloudinary manual (HMAC-SHA1 sobre los parámetros, sin SDK — ver `app/api/routes.py::sign_cloudinary_upload`). Puerto `8007`.

El esquema de `cinema_admin` se crea con `Base.metadata.create_all` al arrancar (`app/core/database.py::init_schema`) — este servicio nunca lo había necesitado antes porque compartía el esquema ya creado por `catalog-service`.

## API

Todos los endpoints van bajo `/api/v1/admin` y requieren JWT de un usuario admin (`get_current_admin`, que resuelve el usuario contra `user-service` — ver Dependencias — y rechaza tokens en la blacklist de Redis).

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/cloudinary/sign` | Firma una subida directa a Cloudinary (poster de película) |
| POST | `/movies` | Crea película — publica `movie.created` (payload completo + `theater_ids`) |
| GET | `/movies` | Lista películas |
| GET | `/movies/{id}` | Detalle de película |
| PUT | `/movies/{id}` | Actualiza película — publica `movie.updated` (todos los campos que cambiaron) |
| PATCH | `/movies/{id}/toggle` | Activa/desactiva película — publica `movie.deactivated` solo al desactivar |
| POST | `/movies/{id}/showtimes` | Crea funciones (showtimes) para una película — publica `showtime.created`, un evento por función |
| DELETE | `/movies/{id}/showtimes/{showtime_id}` | Elimina una función — publica `showtime.deleted` |
| POST | `/theaters` | Crea sala/teatro — publica `theater.created` |
| GET | `/theaters` | Lista teatros |
| PATCH | `/theaters/{id}/toggle` | Activa/desactiva teatro — publica `theater.toggled` |
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

Solo publica — no consume nada. Todos van con `key` = id de la entidad (garantiza orden entre eventos de la misma película/teatro/función — ver `../ARCHITECTURE.md`, Decisión 6.2). Ver el contrato completo (payload, semántica) en `../kafka-schemas-cinema/event_contracts_operativos.md`. `user.deactivated` ya no lo publica este servicio — desde el caso 2 lo publica `user-service`, que es quien aplica el cambio.

| Topic | Cuándo |
|---|---|
| `movie.created` | Al crear una película — payload es el `Movie` completo (no solo el subconjunto de `booking-service`), más `theater_ids` |
| `movie.updated` | Al editar campos de una película — solo los campos que cambiaron |
| `movie.deactivated` | Al desactivar una película (no al reactivar) |
| `theater.created` | Al crear un teatro |
| `theater.toggled` | Al activar/desactivar un teatro |
| `showtime.created` | Al crear funciones — un evento por función, no un batch |
| `showtime.deleted` | Al eliminar una función |

## Variables de entorno clave

| Variable | Para qué |
|---|---|
| `DATABASE_URL_ADMIN` | Conexión a `cinema_admin`, propia de este servicio (películas, teatros, funciones) |
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
- **Kafka** → `catalog-service` (`movie.*`/`theater.*`/`showtime.*`) y `booking-service` (`movie.*`): así se enteran de cambios hechos aquí sin consultar `cinema_admin` directamente. Desde 2026-09-19, `catalog-service` sí los consume — antes compartía la misma base y no le hacían falta (caso 1 de la misma decisión).

Ya no comparte ninguna base de datos con otro servicio.

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

## Flujo de trabajo: Gitflow

| Rama        | Sale de   | Entra a (vía PR)         | Método en GitHub | Para |
| ----------- | --------- | ------------------------ | ---------------- | ---- |
| `main`      | —         | —                        | —                | Lo que está en producción. Cada merge es una versión. |
| `develop`   | `main`    | —                        | —                | Integración de lo próximo a publicar. Rama por defecto. |
| `feature/*` | `develop` | `develop`                | **Squash**       | Una funcionalidad o cambio: `feature/mi-cambio`. |
| `release/*` | `develop` | `main` y luego `develop` | **Merge** a `main`; **Squash** a `develop` | Preparar una versión: `release/1.0.0`. Solo ajustes finales. |
| `hotfix/*`  | `main`    | `main` y luego `develop` | **Merge** a `main`; **Squash** a `develop` | Corrección urgente en producción. |

- **Nadie hace push directo** a `main` ni a `develop`: todo entra por pull request, con los checks de CI en verde.
- **En `develop` se usa squash:** cada feature queda como un solo commit con el título del PR.
- **En `main` se usa merge commit:** cada release o hotfix queda visible como una unidad.
- **Todavía no hay releases:** la app no está completa, así que `main` se queda como está hasta el
  primer `release/*`. Desde entonces, cada versión se etiqueta en `main` (`git tag -a v1.0.0`) con
  [versionado semántico](https://semver.org/lang/es/).

```bash
git switch develop && git pull
git switch -c feature/mi-cambio
# ...commits...
git push -u origin feature/mi-cambio   # abrir PR hacia develop → Squash and merge
```

## CI/CD

GitHub Actions (`.github/workflows/`) corre en cada PR hacia `main` o `develop`. Los rulesets exigen
estos checks; si se renombra un job, hay que actualizar `.github/rulesets/*.json`.

| Check | Qué revisa |
| ----- | ---------- |
| `Lint` | Ruff con las reglas de `ruff.toml`. |
| `Calidad y build` | Instala las dependencias, compila todo el código y carga la app con configuración falsa (sin base de datos ni Kafka). |
| `Imagen Docker` | Construye la imagen y comprueba que la app carga dentro de ella, sin red. |

Con cada push a `develop` o `main` (es decir, al fusionar un PR), y solo si pasaron los checks, se
publica en Docker Hub **la misma imagen que se probó** (no se reconstruye):

- `develop` → `<usuario>/admin-service-cinema:develop` y `:<sha>`
- `main` → `<usuario>/admin-service-cinema:latest` y `:<sha>`

El flujo no despliega en ningún servicio (tampoco en Render): solo publica la imagen.

### Configuración en GitHub (una vez)

- **Rulesets:** `main` y `develop` se protegen importando `.github/rulesets/main.json` y
  `.github/rulesets/develop.json` en *Settings → Rules → Rulesets → Import a ruleset*. Exigen PR, los
  checks de la tabla de arriba, y no permiten borrar la rama ni forzar pushes. `main` solo acepta
  merge commit y `develop` solo squash.
- **Settings → General:** rama por defecto `develop`; permitir merge commits y squash (no rebase);
  activar *Automatically delete head branches*.
- **Secrets** (*Settings → Secrets and variables → Actions*): `DOCKER_USERNAME` y `DOCKER_TOKEN`
  (token de acceso de Docker Hub con permiso de escritura).
