# AI Document Processing API

Backend for an AI document-processing product: users register, authenticate, upload documents, track async processing jobs, receive real-time SSE updates, and fetch processing results. Built as a layered FastAPI app (config → schemas → SQLAlchemy models → Alembic → routes → services) so the same patterns show up in interviews and production services.

**Live now:** JWT auth, document CRUD with ownership, async background processing, job status, SSE streaming, processing results, global error handling, and **19 pytest integration tests**.

For detailed walkthroughs of every flow, see **[FLOWS.md](FLOWS.md)**.

Schema changes go through **Alembic**. Do not create tables by hand in PostgreSQL.

## Table of contents

- [Roadmap]
- [Architecture]
- [Product flow]
- [Folder structure]
  - [Root files]
  - [Alembic]
  - [App]
  - [App core]
  - [App db]
  - [App models]
  - [App schemas]
  - [App api]
  - [App services]
  - [Tests]
- [Requirements]
- [Setup]
- [Configuration]
- [Database]
  - [Mapping]
  - [Start PostgreSQL]
  - [Apply tables with Alembic]
  - [Inspect tables and rows]
- [Authentication]
- [Run]
- [Endpoints]
- [Testing]
- [Error handling]

[Roadmap]: #roadmap
[Architecture]: #architecture
[Product flow]: #product-flow
[Folder structure]: #folder-structure
[Root files]: #root-files
[Alembic]: #alembic
[App]: #app
[App core]: #app-core
[App db]: #app-db
[App models]: #app-models
[App schemas]: #app-schemas
[App api]: #app-api
[App services]: #app-services
[Tests]: #tests
[Requirements]: #requirements
[Setup]: #setup
[Configuration]: #configuration
[Database]: #database
[Mapping]: #mapping
[Start PostgreSQL]: #start-postgresql
[Apply tables with Alembic]: #apply-tables-with-alembic
[Inspect tables and rows]: #inspect-tables-and-rows
[Authentication]: #authentication
[Run]: #run
[Endpoints]: #endpoints
[Testing]: #testing
[Error handling]: #error-handling

## Roadmap

| Step | Topic | Status |
| --- | --- | --- |
| 1 | Project setup | Done |
| 2 | Configuration | Done |
| 3 | Pydantic schemas | Done |
| 4 | PostgreSQL + SQLAlchemy + Alembic | Done |
| 5 | User registration + password hashing | Done |
| 6 | JWT authentication | Done |
| 7 | Document CRUD + authorization | Done |
| 8 | Async processing jobs | Done |
| 9 | SSE / real-time updates | Done |
| 10 | Testing + error handling | Done |

**Overall progress:** 10 / 10 steps (100%)

| Step | What was built |
| --- | --- |
| 1–2 | FastAPI app, `.env` config via `pydantic-settings` |
| 3 | Pydantic schemas for users, auth, documents, jobs |
| 4 | Async SQLAlchemy engine, `get_db`, models, Alembic migrations |
| 5 | `POST /auth/register`, Argon2 password hashing, duplicate-email `409` |
| 6 | JWT login, `get_current_user`, `GET /users/me`, token rejection (`401`) |
| 7 | Document CRUD with ownership (`401` / `403` / `404`) |
| 8 | Background processing on document create, `GET /jobs/{id}`, `GET /documents/{id}/result` |
| 9 | SSE stream at `GET /documents/{id}/events` (push status updates) |
| 10 | Global exception handlers, DB rollback, pytest suite (19 tests) |

## Architecture

```text
Client (curl / Swagger / EventSource)
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  app/api/v1/          HTTP routes                       │
│  auth, users, documents, jobs                           │
└─────────────────┬───────────────────────────────────────┘
                  │ Depends()
        ┌─────────┴─────────┐
        ▼                   ▼
┌───────────────┐   ┌───────────────────┐
│ app/schemas/  │   │ app/core/         │
│ API contract  │   │ config, security, │
│ (Pydantic)    │   │ dependencies,     │
└───────────────┘   │ exception_handlers│
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │ app/services/ │ │ app/db/       │ │ tests/        │
    │ processing,   │ │ engine,get_db │ │ pytest suite  │
    │ event_bus,sse │ └───────┬───────┘ └───────────────┘
    └───────────────┘         │
                              ▼
                    ┌───────────────────┐
                    │ app/models/       │
                    │ SQLAlchemy tables │
                    └─────────┬─────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
      ┌───────────────┐               ┌───────────────┐
      │ alembic/      │               │ PostgreSQL    │
      │ migrations    │──────────────▶│ ai_document_db│
      └───────────────┘               └───────────────┘
```

| Layer | Folder | Responsibility |
| --- | --- | --- |
| Routes | `app/api/v1/` | HTTP endpoints, status codes, wire dependencies |
| Validation | `app/schemas/` | Request/response shapes (Pydantic) |
| Security | `app/core/` | Settings, hashing, JWT, auth deps, error handlers |
| Services | `app/services/` | Background processing, SSE event bus |
| Database access | `app/db/` | Engine, sessions, rollback on error |
| Persistence | `app/models/` | Table definitions, relationships |
| Migrations | `alembic/` | Versioned schema changes |
| Tests | `tests/` | Integration tests via `httpx` + `pytest` |

## Product flow

```text
Client
  ↓
JWT Authentication          POST /auth/register, /auth/login
  ↓
Document CRUD               POST/GET/PATCH/DELETE /documents
  ↓
Async Processing            Background task on document create
  ↓
Processing Jobs             GET /jobs/{job_id}
  ↓
SSE Updates                 GET /documents/{id}/events
  ↓
Processing Results          GET /documents/{id}/result
  ↓
Error Handling              Uniform { detail, error_type }
  ↓
Tests                       pytest -v (19 tests)
```

See **[FLOWS.md](FLOWS.md)** for step-by-step walkthroughs of every flow.

## Folder structure

```text
FastAPI/
├── .env                              # secrets (not committed)
├── .venv/                            # virtual environment (not committed)
├── alembic.ini
├── README.md
├── FLOWS.md                          # detailed flow walkthroughs
├── pytest.ini
├── requirements-dev.txt              # pytest, pytest-asyncio, httpx
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 588879d6d700_create_initial_tables.py
├── tests/
│   ├── conftest.py                   # fixtures, auth helpers
│   ├── test_api.py
│   ├── test_auth.py
│   ├── test_documents.py
│   ├── test_errors.py
│   └── test_sse.py
└── app/
    ├── main.py                       # FastAPI entrypoint + exception handlers
    ├── api/v1/
    │   ├── auth.py                   # register, login
    │   ├── users.py                  # /users/me
    │   ├── documents.py              # CRUD + SSE + result
    │   └── jobs.py                   # job status
    ├── core/
    │   ├── config.py
    │   ├── security.py
    │   ├── dependencies.py           # get_current_user, ownership
    │   ├── errors.py                 # error_type constants
    │   └── exception_handlers.py     # global error handlers
    ├── db/
    │   └── database.py
    ├── models/
    │   ├── user.py
    │   ├── document.py
    │   ├── processing_job.py
    │   └── processing_result.py
    ├── schemas/
    │   ├── auth.py
    │   ├── user.py
    │   ├── document.py
    │   ├── job.py
    │   └── error.py
    └── services/
        ├── processing.py             # background worker
        ├── event_bus.py              # SSE pub/sub
        └── sse.py                    # SSE stream helpers
```

### Root files

| Path | Work |
| --- | --- |
| `.env` | Local secrets: app name, database URL, JWT settings. Loaded by `Settings`. Never commit. |
| `.venv/` | Python virtual environment created by `python -m venv .venv`. Activate before running the app. |
| `alembic.ini` | Alembic CLI config. Database URL is injected at runtime from `settings.database_url` in `alembic/env.py`. |
| `README.md` | Project docs, setup, architecture, and API reference. |

### Alembic

Migration tool. Turns SQLAlchemy models into versioned PostgreSQL schema changes.

| Path | Work |
| --- | --- |
| `env.py` | Runtime for every Alembic command. Sets `sqlalchemy.url` from `settings.database_url` and `target_metadata` from `Base.metadata`. Imports `app.models` so all tables are visible to autogenerate. Uses the async engine (`postgresql+asyncpg`). |
| `script.py.mako` | Template Alembic uses when you run `alembic revision`. |
| `versions/` | One Python file per schema change. Apply with `alembic upgrade head`. Never create the same tables by hand in Postgres. |

### App

Application package. This is what Uvicorn loads (`app.main:app`).

| Path | Work |
| --- | --- |
| `main.py` | Creates `FastAPI` app, registers exception handlers, mounts all routers at `/api/v1`, exposes `/` and `/health`. |

### App api

HTTP routers. Each file defines an `APIRouter` included from `main.py`.

| Path | Endpoints | Key dependencies |
| --- | --- | --- |
| `v1/auth.py` | `POST /auth/register`, `POST /auth/login` | `get_db`, `hash_password`, `verify_password`, `create_access_token` |
| `v1/users.py` | `GET /users/me` | `get_current_user` |
| `v1/documents.py` | `POST/GET/PATCH/DELETE /documents`, `GET /documents/{id}/events`, `GET /documents/{id}/result` | `get_current_user`, `get_owned_document`, `BackgroundTasks` |
| `v1/jobs.py` | `GET /jobs/{job_id}` | `get_owned_job` |

**Request flow example (login):**

```text
POST /api/v1/auth/login
  → LoginRequest (Pydantic)
  → select User by email
  → verify_password()
  → create_access_token(user.id)
  → TokenResponse
```

### App core

Cross-cutting app configuration and security.

| Path | Functions / symbols | Purpose |
| --- | --- | --- |
| `config.py` | `Settings`, `settings` | Load `.env` into typed settings |
| `security.py` | `hash_password`, `verify_password`, `create_access_token`, `decode_access_token` | Password hashing (Argon2) and JWT create/verify |
| `dependencies.py` | `get_current_user`, `get_owned_document`, `get_owned_job`, `get_current_user_sse` | Bearer → User; ownership checks |
| `errors.py` | `error_type_for_status`, constants | Machine-readable error categories |
| `exception_handlers.py` | `register_exception_handlers` | Uniform JSON error responses |

### App db

Database infrastructure: how Python talks to PostgreSQL.

| Path | Exports / symbols | Purpose |
| --- | --- | --- |
| `database.py` | `Base`, `engine`, `AsyncSessionLocal`, `get_db` | Async engine, declarative base, per-request session with rollback on error |

### App models

SQLAlchemy models = **database contract** (tables, columns, FKs). Not used as API request/response bodies.

| Path | Model | Table | Relationships |
| --- | --- | --- | --- |
| `user.py` | `User` | `users` | → many `documents` |
| `document.py` | `Document` | `documents` | → `user`; many `processing_jobs`; one `processing_result` |
| `processing_job.py` | `ProcessingJob` | `processing_jobs` | → `document` |
| `processing_result.py` | `ProcessingResult` | `processing_results` | → `document` (1:1, PK = `document_id`) |

### App schemas

Pydantic models = **API contract** (validate request JSON, shape responses). Separate from SQLAlchemy so the HTTP API can change without rewriting tables.

| Path | Schemas | Used by |
| --- | --- | --- |
| `auth.py` | `LoginRequest`, `TokenResponse` | `POST /auth/login` |
| `user.py` | `UserCreate`, `UserResponse` | `POST /auth/register`, `GET /users/me` |
| `document.py` | `DocumentCreate`, `DocumentUpdate`, `DocumentResponse`, `DocumentStatus` | Document CRUD |
| `job.py` | `ProcessingJobResponse`, `ProcessingResultResponse`, `ProcessingJobStatus` | Jobs and results |
| `error.py` | `ErrorResponse` | Error response shape |

### App services

Background processing and real-time updates.

| Path | Role |
| --- | --- |
| `processing.py` | `process_document_job` — word/character counts in background |
| `event_bus.py` | In-memory pub/sub per `document_id` |
| `sse.py` | SSE frame formatting and stream generator |

### Tests

| Path | Covers |
| --- | --- |
| `conftest.py` | `AsyncClient`, `auth_client`, helpers |
| `test_api.py` | `/`, `/health` |
| `test_auth.py` | Register, login, JWT |
| `test_documents.py` | CRUD, isolation, processing |
| `test_errors.py` | Status codes, `error_type` |
| `test_sse.py` | SSE stream, query-token auth |

## Requirements

- Python 3.12+
- PostgreSQL with a database named `ai_document_db` (or change `DATABASE_URL`)

## Setup

```bash
python -m venv .venv
```

Activate the virtual environment:

**Git Bash**

```bash
source .venv/Scripts/activate
```

**PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install fastapi uvicorn pydantic-settings email-validator sqlalchemy asyncpg alembic "pwdlib[argon2]" PyJWT
pip install -r requirements-dev.txt   # optional: for running tests
```

## Configuration

Settings are loaded from `.env`:

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | API title |
| `APP_ENV` | Environment name (`development`, etc.) |
| `DEBUG` | FastAPI debug flag |
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://...`) |
| `JWT_SECRET_KEY` | Secret used to sign JWTs (use a long random value in production) |
| `JWT_ALGORITHM` | JWT signing algorithm (default `HS256`) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime in minutes |

Keep credentials in `.env` only. Do not commit secrets.

Example:

```env
APP_NAME=AI Document Processing API
APP_ENV=development
DEBUG=true
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_document_db
JWT_SECRET_KEY=your-development-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Database

### Mapping

**Environment → app**

| `.env` | Settings field | Used by |
| --- | --- | --- |
| `APP_NAME` | `settings.app_name` | FastAPI title, `GET /` |
| `APP_ENV` | `settings.app_env` | `GET /health` |
| `DEBUG` | `settings.debug` | FastAPI debug flag |
| `DATABASE_URL` | `settings.database_url` | SQLAlchemy engine + Alembic |
| `JWT_SECRET_KEY` | `settings.jwt_secret_key` | Sign and verify JWTs |
| `JWT_ALGORITHM` | `settings.jwt_algorithm` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `settings.jwt_access_token_expire_minutes` | Token lifetime |

**`DATABASE_URL` parts**

```text
postgresql+asyncpg://postgres:postgres@localhost:5432/ai_document_db
│                  │         │        │         │    │
│                  │         │        │         │    └─ database name
│                  │         │        │         └─ port
│                  │         │        └─ host
│                  │         └─ password
│                  └─ username
└─ driver (async SQLAlchemy + asyncpg)
```

**Request → Postgres (protected route)**

```text
GET /api/v1/users/me
  → Authorization: Bearer <JWT>
  → HTTPBearer
  → decode_access_token()   # signature + exp + sub
  → select User by id
  → UserResponse            # id, email, created_at only
```

**Models vs schemas**

| Layer | Folder | Job |
| --- | --- | --- |
| API contract | `app/schemas/` | Validate JSON in/out. Password stays a secret here; never returned. |
| Database contract | `app/models/` | Tables and columns. User stores `password_hash`, not plain `password`. |
| Schema versions | `alembic/versions/` | SQL that creates/alters those tables in Postgres. |

**Python class → Postgres table**

| SQLAlchemy model | Table | Notes |
| --- | --- | --- |
| `User` | `users` | Unique `email`; `password_hash` |
| `Document` | `documents` | `user_id` → `users.id` |
| `ProcessingJob` | `processing_jobs` | `document_id` → `documents.id` (many jobs per document) |
| `ProcessingResult` | `processing_results` | `document_id` is PK (one result per document) |

```text
users
  └── documents
        ├── processing_jobs
        └── processing_results
```

```text
.env  →  Settings  →  create_async_engine()  →  get_db()
models  →  Base.metadata  →  alembic revision --autogenerate  →  alembic upgrade  →  Postgres tables
```

### Start PostgreSQL

**Option A — Docker** (simplest if Docker Desktop is installed)

```bash
docker run --name ai-postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ai_document_db -p 5432:5432 -d postgres:16
```

Start it later:

```bash
docker start ai-postgres
```

Stop it:

```bash
docker stop ai-postgres
```

**Option B — PostgreSQL installed on Windows**

1. Open **Services** (`Win + R` → `services.msc`).
2. Find a service named like **postgresql-x64-16**.
3. Start it (or run in PowerShell as Administrator):

```powershell
net start postgresql-x64-16
```

The exact service name depends on the version you installed.

Then create the database once (if it does not exist):

```bash
psql -U postgres -c "CREATE DATABASE ai_document_db;"
```

### Apply tables with Alembic

Postgres must be running. From the project root with the venv active:

```bash
alembic upgrade head
```

That creates `users`, `documents`, `processing_jobs`, `processing_results`, and `alembic_version`. Do not `CREATE TABLE` by hand.

If you change a model later:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

### Inspect tables and rows

Connect (password is `postgres` if you used the `.env` example):

```bash
psql -U postgres -h localhost -p 5432 -d ai_document_db
```

Useful `psql` commands:

| Command | What it shows |
| --- | --- |
| `\l` | All databases |
| `\c ai_document_db` | Switch to this project's database |
| `\dt` | Tables |
| `\d users` | Columns, PK, indexes on `users` |
| `\d documents` | Columns and foreign keys on `documents` |
| `\d processing_jobs` | Job table definition |
| `\d processing_results` | Result table definition |
| `\di` | Indexes |
| `\q` | Quit |

Example queries:

```sql
SELECT * FROM users;
SELECT * FROM documents;
SELECT * FROM processing_jobs;
SELECT * FROM processing_results;
SELECT * FROM alembic_version;   -- which migration is applied

SELECT d.id, d.title, d.status, u.email
FROM documents d
JOIN users u ON u.id = d.user_id;
```

**pgAdmin:** connect to `localhost:5432` → database `ai_document_db` → **Schemas** → **public** → **Tables**. Right-click a table → **View/Edit Data** → **All Rows**.

**One-shot from the terminal** (no interactive prompt):

```bash
psql -U postgres -h localhost -d ai_document_db -c "\dt"
psql -U postgres -h localhost -d ai_document_db -c "SELECT id, email, password_hash FROM users;"
```

## Authentication

Full auth chain (Steps 5–6):

```text
POST /register  →  UserCreate  →  hash_password()  →  users table
POST /login     →  LoginRequest  →  verify_password()  →  JWT (sub + exp)
GET /users/me   →  Authorization: Bearer <JWT>  →  get_current_user()  →  UserResponse
```

**Protected routes** use `Depends(get_current_user)`. Document and job routes additionally enforce ownership via `get_owned_document` / `get_owned_job`.

**Security rules**

- Passwords are hashed with Argon2 (`pwdlib`). Plain passwords are never stored.
- Login returns the same `401` message for unknown email and wrong password (no email enumeration).
- `UserResponse` exposes `id`, `email`, `created_at` only — never `password_hash`.
- Invalid, expired, or missing tokens return `401 Unauthorized`.
- Document `user_id` comes from the JWT — never from the request body.
- Another user's document returns `403 Forbidden`; missing document returns `404 Not Found`.

**Token rejection cases (verified)**

| Case | Example | Status |
| --- | --- | --- |
| Missing token | No `Authorization` header | `401` |
| Malformed header | `Authorization: Something abc123` | `401` |
| Invalid JWT | `Bearer this-is-not-a-jwt` | `401` |
| Expired JWT | `exp` in the past | `401` |
| Valid JWT, user deleted | `sub` not in `users` table | `401` |

**Registration / login validation**

| Case | Status |
| --- | --- |
| Valid registration | `201` |
| Duplicate email | `409` |
| Invalid email / short password | `422` |
| Wrong password / unknown email on login | `401` (same message) |

**Quick test (Swagger or curl)**

```bash
# Register
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"vipul@example.com","password":"StrongPassword123"}'

# Login
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"vipul@example.com","password":"StrongPassword123"}'

# Current user (replace TOKEN)
curl http://127.0.0.1:8000/api/v1/users/me \
  -H "Authorization: Bearer TOKEN"
```

## Run

From the project root, with the venv active:

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Endpoints

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/` | No | App name |
| `GET` | `/health` | No | Status and environment |
| `POST` | `/api/v1/auth/register` | No | `201` — create user → `UserResponse` |
| `POST` | `/api/v1/auth/login` | No | `200` — login → `access_token`, `token_type: bearer` |
| `GET` | `/api/v1/users/me` | Bearer JWT | `200` — current user (`id`, `email`, `created_at`) |
| `POST` | `/api/v1/documents` | Bearer JWT | `201` — create document + enqueue processing job |
| `GET` | `/api/v1/documents` | Bearer JWT | `200` — list own documents only |
| `GET` | `/api/v1/documents/{id}` | Bearer JWT | `200` / `403` / `404` — get one document |
| `PATCH` | `/api/v1/documents/{id}` | Bearer JWT | `200` — partial update |
| `DELETE` | `/api/v1/documents/{id}` | Bearer JWT | `204` — delete document |
| `GET` | `/api/v1/documents/{id}/events` | Bearer JWT or `?access_token=` | SSE stream: `queued` → `processing` → `completed` |
| `GET` | `/api/v1/documents/{id}/result` | Bearer JWT | `200` — word/character counts (after job completes) |
| `GET` | `/api/v1/jobs/{job_id}` | Bearer JWT | `200` — processing job status |

**Document create flow**

```text
POST /documents  →  201 immediately
        ↓
Background task: queued → processing → completed
        ↓
SSE clients receive live updates
        ↓
GET /documents/{id}/result  →  word_count, character_count
```

**SSE example (curl)**

```bash
curl -N -H "Authorization: Bearer TOKEN" \
  http://127.0.0.1:8000/api/v1/documents/DOCUMENT_ID/events
```

## Testing

Install dev dependencies and run the full suite:

```bash
pip install -r requirements-dev.txt
pytest -v
```

**19 tests** cover auth, CRUD, ownership, processing, SSE, and error responses. Tests use the PostgreSQL database from `.env`.

| Module | What it tests |
| --- | --- |
| `test_api.py` | Root and health endpoints |
| `test_auth.py` | Register, login, `/users/me`, invalid token |
| `test_documents.py` | CRUD, user isolation, job + result |
| `test_errors.py` | Status codes and `error_type` field |
| `test_sse.py` | SSE auth, completed snapshot, query-token |

## Error handling

All errors return a consistent JSON shape:

```json
{
  "detail": "Document not found",
  "error_type": "not_found"
}
```

| Situation | Status | `error_type` |
| --- | --- | --- |
| Missing/invalid JWT | `401` | `unauthorized` |
| Not owner | `403` | `forbidden` |
| Resource not found | `404` | `not_found` |
| Duplicate email | `409` | `conflict` |
| Validation failed | `422` | `validation_error` |
| Database error | `500` | `database_error` |

`get_db()` rolls back the session on any exception. Global handlers live in `app/core/exception_handlers.py`.
