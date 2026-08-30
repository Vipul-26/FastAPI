# How this API works — all flows in one place

Read this file when you want the full picture. Code lives in the files named under each flow.

---

## 0. Layers (mental model)

```text
Client (browser / curl / Swagger)
        ↓  JSON over HTTP
Routes          app/api/v1/*.py          what URLs do
        ↓
Schemas         app/schemas/*.py         validate JSON in/out
        ↓
Security        app/core/security.py     hash passwords, sign/verify JWT
Dependencies    app/core/dependencies.py turn Bearer token → User
        ↓
Models          app/models/*.py          Python map of database tables
        ↓
Session         app/db/database.py       get_db() → PostgreSQL
        ↓
PostgreSQL      tables created by Alembic
```

**Model** = what is stored in the database.  
**Schema** = what the API accepts and returns (JSON).  
**Route** = glue between them.

---

## 0.1 Full architecture pipeline

End-to-end product flow (all 10 roadmap steps):

```text
Client
  ↓
JWT Authentication          POST /auth/register, /auth/login
  ↓                         Bearer token on protected routes
Document CRUD               POST/GET/PATCH/DELETE /documents
  ↓
Async Processing            Background task on document create
  ↓
Processing Jobs             GET /jobs/{job_id}  (poll status)
  ↓
SSE Updates                 GET /documents/{id}/events  (push status)
  ↓
Processing Results          GET /documents/{id}/result  (word/char counts)
  ↓
Error Handling              Uniform { detail, error_type } on all errors
  ↓
Tests                       pytest -v  (19 tests)
```

**Happy path (create → result):**

```text
Client                    API                         Background worker
  │                        │                                │
  ├── POST /auth/login ───►│ issue JWT                      │
  │◄── access_token ───────┤                                │
  │                        │                                │
  ├── POST /documents ────►│ create doc + job (queued)      │
  │◄── 201 + doc ──────────┤ publish SSE "queued"           │
  │                        ├── add_task(process_document_job)►│
  │                        │                                │ processing
  ├── GET .../events ─────►│ stream SSE ◄── event bus ◄─────┤ publish updates
  │◄── queued/processing/completed ──────────────────────────┤
  │                        │                                │ save result
  ├── GET .../result ─────►│                                │
  │◄── { word_count, character_count } ──────────────────────┤
```

| Layer | Key endpoints | Key files |
|-------|---------------|-----------|
| JWT Auth | `/auth/register`, `/auth/login`, `/users/me` | `security.py`, `dependencies.py`, `auth.py` |
| Document CRUD | `/documents` | `documents.py`, `schemas/document.py` |
| Async Processing | triggered on `POST /documents` | `processing.py` |
| Processing Jobs | `/jobs/{job_id}` | `jobs.py`, `models/processing_job.py` |
| SSE Updates | `/documents/{id}/events` | `event_bus.py`, `sse.py` |
| Processing Results | `/documents/{id}/result` | `models/processing_result.py` |
| Error Handling | wraps every route | `exception_handlers.py`, `errors.py` |
| Tests | `pytest -v` | `tests/test_*.py` |

**Roadmap: 10/10 complete.**

---

## 1. App startup

```text
uvicorn app.main:app --reload
        ↓
app/main.py creates FastAPI(title=..., debug=...)
        ↓
include_router(auth)      →  /api/v1/auth/...
include_router(users)     →  /api/v1/users/...
include_router(documents) →  /api/v1/documents/...
include_router(jobs)      →  /api/v1/jobs/...
        ↓
GET /        → app name
GET /health  → { status, environment }
```

**Files:** `app/main.py`, `app/core/config.py`

---

## 2. Configuration (`.env` → Settings)

```text
.env file on disk
        ↓
pydantic-settings reads it
        ↓
settings = Settings()     (one shared object)
        ↓
Used by: database engine, JWT sign/verify, app title
```

| `.env` variable | Python field | Used for |
|-----------------|--------------|----------|
| `APP_NAME` | `app_name` | FastAPI title, `/` |
| `APP_ENV` | `app_env` | `/health` |
| `DEBUG` | `debug` | FastAPI debug |
| `DATABASE_URL` | `database_url` | PostgreSQL connection |
| `JWT_SECRET_KEY` | `jwt_secret_key` | Sign and verify tokens (you generate this) |
| `JWT_ALGORITHM` | `jwt_algorithm` | Usually `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `jwt_access_token_expire_minutes` | Token lifetime (30) |

You do **not** download `JWT_SECRET_KEY`. Generate a random string (32+ chars) and put it in `.env`.

**Files:** `.env`, `app/core/config.py`

---

## 3. PostgreSQL connection

```text
DATABASE_URL in .env
  postgresql+asyncpg://user:password@localhost:5432/ai_document_db
        ↓
settings.database_url
        ↓
create_async_engine(...)     connection pool
        ↓
AsyncSessionLocal            session factory
        ↓
get_db()                     one session per HTTP request
        ↓
Route: db: AsyncSession = Depends(get_db)
        ↓
session closed when the request ends
```

**Files:** `app/db/database.py`

---

## 4. Alembic (schema migrations)

Alembic is version control for **tables**, not for row data.

```text
Python models (app/models/*.py)
        ↓
alembic revision --autogenerate
        ↓
File in alembic/versions/   (e.g. create users, documents, ...)
        ↓
alembic upgrade head
        ↓
PostgreSQL now has the tables
```

```text
alembic/env.py
        ↓
same DATABASE_URL as the app
        ↓
Base.metadata  (all models imported)
        ↓
compare models vs live DB → write/apply SQL
```

| Command | Meaning |
|---------|---------|
| `alembic upgrade head` | Apply all pending table changes |
| `alembic downgrade -1` | Undo last change |
| `alembic current` | Which revision the DB is on |

**Files:** `alembic/env.py`, `alembic/versions/588879d6d700_create_initial_tables.py`

---

## 5. Models vs schemas

```text
Client sends JSON
        ↓
UserCreate / LoginRequest     schema — includes plaintext password
        ↓
User model                    table row — password_hash only
        ↓
UserResponse / TokenResponse  schema — never sends password_hash
        ↓
Client receives JSON
```

| Piece | File | Contains password? |
|-------|------|-------------------|
| `UserCreate` | `app/schemas/user.py` | Yes (plaintext, inbound only) |
| `User` | `app/models/user.py` | Hash only (`password_hash`) |
| `UserResponse` | `app/schemas/user.py` | No |
| `LoginRequest` | `app/schemas/auth.py` | Yes (plaintext, inbound only) |
| `TokenResponse` | `app/schemas/auth.py` | No — JWT string |
| `DocumentCreate` | `app/schemas/document.py` | No — `title` + `content` only |
| `Document` | `app/models/document.py` | Has `user_id` (owner), not sent by client |
| `DocumentResponse` | `app/schemas/document.py` | No `user_id` in JSON (for now) |

### Register / document response filtering

The route may `return` a SQLAlchemy object with **more** fields than the client sees.
`response_model=UserResponse` or `DocumentResponse` copies only the fields listed on the schema.

Example: `User` has `password_hash` in PostgreSQL, but `UserResponse` only exposes `id`, `email`, `created_at`.

---

## 6.1 Password hashing

Never store `"MyPassword123"`. Store a **one-way hash**.

```text
Plain password
        ↓
hash_password()     Argon2 + random salt  (pwdlib)
        ↓
"$argon2id$v=19$m=65536,t=3,p=4$...."
        ↓
PostgreSQL users.password_hash
```

Hashing is **not** encryption. Encryption can be reversed. A hash cannot.

Same password hashed twice → **different** strings (new salt each time). That is expected.

Do not use plain SHA-256 for passwords: it is too fast for attackers.

**File:** `app/core/security.py` → `hash_password()`

---

## 6.2 User registration

`POST /api/v1/auth/register`

```text
JSON { email, password }
        ↓
UserCreate  (EmailStr, password min 8)     invalid → 422
        ↓
SELECT user WHERE email = ...
        ↓
Already exists? → 409 "Email already registered"
        ↓
hash_password(password) → password_hash
        ↓
User(email, password_hash)
        ↓
db.add → commit → refresh   (id, created_at from DB)
        ↓
UserResponse { id, email, created_at }     201
```

PostgreSQL has the Argon2 hash. The JSON response does **not** include the password or the hash.

**Files:** `app/api/v1/auth.py` → `register()`, `app/schemas/user.py`

---

## 6.3 Password verification (login)

`POST /api/v1/auth/login`

The original password is never recovered. Verify re-hashes the typed password with the **salt inside the stored hash** and compares.

```text
JSON { email, password }
        ↓
LoginRequest
        ↓
SELECT User by email
        ↓
user is None  ──────────────┐
        ↓                   │
verify_password(            │
  typed password,           │
  user.password_hash        │
)                           │
        ↓                   │
False  ─────────────────────┤
        ↓                   ↓
True → credentials OK     401 "Invalid email or password"
        ↓
create_access_token(user.id)     (6.4)
```

Wrong email and wrong password use the **same** 401 message so attackers cannot discover which emails exist.

**Files:** `app/api/v1/auth.py` → `login()`, `app/core/security.py` → `verify_password()`

---

## 6.4 JWT creation

A JWT is three Base64 parts: `header.payload.signature`.

Anyone can read the payload. Only the server with `JWT_SECRET_KEY` can create a valid signature.

```text
user.id
        ↓
payload = { sub: "<uuid>", exp: now + 30 minutes }
        ↓
jwt.encode(payload, JWT_SECRET_KEY, HS256)
        ↓
"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...."
        ↓
{ "access_token": "eyJ...", "token_type": "bearer" }
```

| Claim | Meaning |
|-------|---------|
| `sub` | Subject = user UUID |
| `exp` | Expiry time (UTC) |

**Files:** `app/core/security.py` → `create_access_token()`, `.env` JWT settings

---

## 6.5 JWT validation

Opposite of 6.4. Do **not** decode and trust the payload without verifying the signature.

```text
JWT string
        ↓
jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        ↓
Signature invalid? → reject
Expired (exp)?     → reject
Missing/bad sub?   → reject
        ↓
UUID from `sub`
```

**File:** `app/core/security.py` → `decode_access_token()` → returns `UUID`

---

## 6.6–6.8 Bearer header → current user → protected route

The client sends the token on later requests:

```http
Authorization: Bearer eyJ...
```

```text
GET /api/v1/users/me
        ↓
HTTPBearer extracts the token          (6.6)
        ↓
decode_access_token(token)             (6.5)
        ↓
SELECT User WHERE id = sub
        ↓
No user / bad token / missing header → 401
        ↓
get_current_user returns User          (6.7)
        ↓
get_me() returns UserResponse          (6.8)
```

`GET /users/me` does not decode the JWT itself. It only declares:

```python
current_user: User = Depends(get_current_user)
```

FastAPI runs `get_current_user` first. `UserResponse` still strips `password_hash`.

### Where `credentials` comes from

`get_current_user` does not read the header itself. FastAPI injects it because of:

```python
credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)
```

`bearer_scheme` is `HTTPBearer(...)`. It looks at `Authorization` on the current request.

```text
Browser / curl / Swagger
        │
        │  Authorization: Bearer eyJ...
        ▼
FastAPI sees GET /users/me
        │
        │  get_me(current_user = Depends(get_current_user))
        ▼
get_current_user needs credentials and db
        │
        ├─ Depends(bearer_scheme)  →  HTTPBearer reads the header
        │                             credentials = HTTPAuthorizationCredentials(...)
        │                             credentials.scheme      = "Bearer"
        │                             credentials.credentials = "eyJ..."
        │
        └─ Depends(get_db)         →  database session
        ▼
get_current_user(credentials, db) runs
        │
        └─ credentials.credentials  →  decode_access_token  →  User
        ▼
get_me(current_user=that User)
```

Missing header → `credentials` is `None` (`auto_error=False`) → **401**.

**Files:**  
- `app/core/dependencies.py` → `bearer_scheme`, `get_current_user()`  
- `app/api/v1/users.py` → `GET /me`

---

## 6.9 Authorization vs ownership

**Authentication** = who are you? (valid JWT → `User`) → **401** if not.  
**Authorization** = are you allowed to touch this resource? → **403** if not.

`GET /users/me` only needs authentication: the resource *is* you.

Documents have an owner column `documents.user_id`. Being logged in is not enough — User A must not read User B’s document.

```text
GET /api/v1/documents/{document_id}
        ↓
get_current_user()              401 if no/invalid token
        ↓
SELECT Document WHERE id = document_id
        ↓
No row?     → 404
        ↓
document.user_id == current_user.id ?
        │
    No  → 403 Forbidden     (logged in, but not the owner)
        │
    Yes → return Document
```

Helper (used by document routes in Step 7):

```python
document: Document = Depends(get_owned_document)
```

`document_id` comes from the URL path. FastAPI injects it into `get_owned_document`.

**File:** `app/core/dependencies.py` → `get_owned_document()`

---

## 7.1 Create document

`POST /api/v1/documents`  
**Auth required:** `Authorization: Bearer <JWT>`

The client sends **only** `title` and `content`. Never accept `user_id` in the JSON body — the owner comes from the JWT.

```http
POST /api/v1/documents
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "title": "My first document",
  "content": "This is some document content."
}
```

```text
Authorization: Bearer <JWT>
        ↓
get_current_user()                    401 if missing/invalid
        ↓
DocumentCreate (title, content)       422 if invalid
        ↓
Document(
    title=document_in.title,
    content=document_in.content,
    user_id=current_user.id,          ← from JWT, NOT from client
)
        ↓
db.add → commit → refresh
        ↓
DocumentResponse                      201
```

**Response `201`:**

```json
{
  "id": "uuid",
  "title": "My first document",
  "content": "This is some document content.",
  "status": "created",
  "created_at": "...",
  "updated_at": "..."
}
```

| Case | Status |
|------|--------|
| Valid token + body | **201** |
| No / bad token | **401** |
| Empty title or content | **422** |

**View in PostgreSQL:**

```bash
psql -U postgres -h localhost -d ai_document_db -c "SELECT id, user_id, title, status FROM documents;"
```

The `user_id` column in the database matches `current_user.id` from the JWT.

**Files:**  
- `app/api/v1/documents.py` → `create_document()`  
- `app/schemas/document.py` → `DocumentCreate`, `DocumentResponse`  
- `app/models/document.py` → `Document` table

**Step 7 progress:** 7.1 done. Upcoming: list, get by id, update, delete.

---

## 7.2 List current user's documents

`GET /api/v1/documents`  
**Auth required:** `Authorization: Bearer <JWT>`

Returns **only** documents where `documents.user_id = current_user.id`. User B never sees User A's rows.

```http
GET /api/v1/documents
Authorization: Bearer eyJ...
```

```text
Authorization: Bearer <JWT>
        ↓
get_current_user()                         401 if missing/invalid
        ↓
SELECT * FROM documents
WHERE user_id = current_user.id
ORDER BY created_at DESC
        ↓
list[DocumentResponse]                     200
```

**Response `200`:**

```json
[
  {
    "id": "uuid",
    "title": "My first document",
    "content": "...",
    "status": "created",
    "created_at": "...",
    "updated_at": "..."
  }
]
```

Empty list `[]` is valid — user has no documents yet.

| Case | Status |
|------|--------|
| Valid token | **200** (array, maybe empty) |
| No / bad token | **401** |

**Files:** `app/api/v1/documents.py` → `list_documents()`

**Step 7 progress:** 7.1–7.2 done. Upcoming: get by id, update, delete.

---

## 7.3 Get document by ID

`GET /api/v1/documents/{document_id}`  
**Auth required:** `Authorization: Bearer <JWT>`

Uses `get_owned_document` — authentication **and** ownership in one dependency.

```http
GET /api/v1/documents/32fd3de1-9225-4858-8448-653d9c780111
Authorization: Bearer eyJ...
```

```text
document_id from URL path
        ↓
get_owned_document(document_id)
        ├─ get_current_user()              401 if no/invalid token
        ├─ SELECT Document WHERE id = ...
        ├─ not found                       404
        ├─ document.user_id != current_user.id   403
        └─ return Document
        ↓
DocumentResponse                         200
```

Route code is short because the dependency does the security work:

```python
@router.get("/{document_id}")
async def get_document(document: Document = Depends(get_owned_document)):
    return document
```

| Case | Status |
|------|--------|
| Owner, document exists | **200** |
| No / bad token | **401** |
| Document does not exist | **404** |
| Exists but owned by another user | **403** |

**Files:**  
- `app/api/v1/documents.py` → `get_document()`  
- `app/core/dependencies.py` → `get_owned_document()`

**Step 7 progress:** 7.1–7.3 done. Upcoming: update, delete.

---

## 7.4 Update document

`PATCH /api/v1/documents/{document_id}`  
**Auth required:** `Authorization: Bearer <JWT>`

Partial update — send only the fields you want to change (`title`, `content`, or both).

```http
PATCH /api/v1/documents/32fd3de1-9225-4858-8448-653d9c780111
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "title": "Updated title"
}
```

```text
document_id from URL
        ↓
get_owned_document()                   401 / 404 / 403
        ↓
DocumentUpdate (optional title/content)
        ↓
model_dump(exclude_unset=True)         only fields client sent
        ↓
setattr on document row
        ↓
commit → refresh
        ↓
DocumentResponse                       200
```

`user_id` and `status` are **not** in `DocumentUpdate` — the client cannot reassign ownership or change processing status through this endpoint.

| Case | Status |
|------|--------|
| Owner, valid body | **200** |
| Owner, update title only | **200** (content unchanged) |
| No / bad token | **401** |
| Not found | **404** |
| Another user's document | **403** |

**Files:**  
- `app/api/v1/documents.py` → `update_document()`  
- `app/schemas/document.py` → `DocumentUpdate`

**Step 7 progress:** 7.1–7.4 done. Upcoming: delete.

---

## 7.5 Delete document

`DELETE /api/v1/documents/{document_id}`  
**Auth required:** `Authorization: Bearer <JWT>`

```http
DELETE /api/v1/documents/32fd3de1-9225-4858-8448-653d9c780111
Authorization: Bearer eyJ...
```

```text
document_id from URL
        ↓
get_owned_document()                   401 / 404 / 403
        ↓
db.delete(document) → commit
        ↓
204 No Content                         (empty body)
```

Deleting a document also removes related rows (cascade): `processing_jobs` and `processing_results` linked to that document.

| Case | Status |
|------|--------|
| Owner, document exists | **204** (no body) |
| GET same id after delete | **404** |
| No / bad token | **401** |
| Not found | **404** |
| Another user's document | **403** |

**Files:** `app/api/v1/documents.py` → `delete_document()`

**Step 7 progress:** 7.1–7.5 done. CRUD complete. Testing (7.7) next.

---

## 7.6 Authorization / ownership (summary)

Every document route enforces two layers:

| Layer | Question | Failure |
|-------|----------|---------|
| Authentication | Valid JWT? | **401** |
| Authorization | Does `document.user_id == current_user.id`? | **403** |

| Endpoint | How ownership is enforced |
|----------|---------------------------|
| `POST /documents` | `user_id = current_user.id` at create time |
| `GET /documents` | SQL `WHERE user_id = current_user.id` |
| `GET/PATCH/DELETE /documents/{id}` | `Depends(get_owned_document)` |

Never accept `user_id` from the client JSON body.

---

## 7.7 Document CRUD tests (checklist)

| # | Action | Expected |
|---|--------|----------|
| 1 | `POST /documents` with token + valid body | **201**, `status: "created"` |
| 2 | `POST /documents` without token | **401** |
| 3 | `POST /documents` empty title | **422** |
| 4 | `GET /documents` — User A vs User B docs | A sees only A's rows |
| 5 | `GET /documents` without token | **401** |
| 6 | `GET /documents/{id}` as owner | **200** |
| 7 | `GET /documents/{id}` as other user | **403** |
| 8 | `GET /documents/{id}` unknown id | **404** |
| 9 | `PATCH /documents/{id}` as owner | **200** |
| 10 | `PATCH /documents/{id}` as other user | **403** |
| 11 | `DELETE /documents/{id}` as owner | **204** |
| 12 | `GET` same id after delete | **404** |
| 13 | `DELETE /documents/{id}` as other user | **403** |
| 14 | PostgreSQL `documents.user_id` | matches JWT user for all owned rows |

**All 14 tests passed** on the live API.

**Step 7 complete.** Next roadmap step: **Step 8 — Processing jobs**.

---

## 8. Async processing / jobs

When a document is created, a background job is queued automatically.

```text
POST /api/v1/documents
        ↓
Create Document (status: created)
        ↓
Create ProcessingJob (status: queued)
        ↓
commit → return DocumentResponse 201
        ↓
BackgroundTasks → process_document_job(job_id)
        ↓
Job status: processing
Document status: processing
        ↓
Calculate word_count + character_count
        ↓
Insert ProcessingResult
        ↓
Job status: completed
Document status: completed
```

### Background worker

`app/services/processing.py` opens its **own** DB session (the request session is already closed).

| Step | What happens |
|------|----------------|
| 1 | Load `ProcessingJob` + `Document` |
| 2 | Set job `processing`, `started_at`; document `processing` |
| 3 | `word_count = len(content.split())`, `character_count = len(content)` |
| 4 | Insert `ProcessingResult` |
| 5 | Set job `completed`, `completed_at`; document `completed` |
| On error | Job `failed`, document `failed`, `error` message saved |

### New endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/jobs/{job_id}` | Poll job status (`queued` → `processing` → `completed`) |
| `GET` | `/api/v1/documents/{document_id}/result` | Word/character counts after job completes |

Both require Bearer JWT and ownership (via `get_owned_job` / `get_owned_document`).

**Example result `200`:**

```json
{
  "document_id": "uuid",
  "word_count": 5,
  "character_count": 26,
  "processed_at": "2026-08-30T...",
  "status": "completed"
}
```

Before processing finishes, `GET .../result` returns **404** `"Processing result not ready yet"`.

### PostgreSQL tables used

```bash
psql -U postgres -h localhost -d ai_document_db -c "SELECT id, document_id, status FROM processing_jobs;"
psql -U postgres -h localhost -d ai_document_db -c "SELECT document_id, word_count, character_count FROM processing_results;"
```

### Files

| File | Role |
|------|------|
| `app/services/processing.py` | Background worker |
| `app/api/v1/documents.py` | Creates job on `POST /documents`; `GET .../result` |
| `app/api/v1/jobs.py` | `GET /jobs/{job_id}` |
| `app/core/dependencies.py` | `get_owned_job()` |
| `app/schemas/job.py` | Job/result response schemas |

---

## 6.10 Authentication tests (checklist)

| # | Action | Expected |
|---|--------|----------|
| 1 | `POST /auth/register` valid | **201**, body has `id`, `email`, `created_at` only |
| 2 | Invalid email | **422** |
| 3 | Password shorter than 8 | **422** |
| 4 | Same email again | **409** |
| 5 | `POST /auth/login` correct password | **200** + JWT that `decode_access_token` accepts |
| 6 | Wrong password | **401** `"Invalid email or password"` |
| 7 | Unknown email | **401** same message |
| 8 | `GET /users/me` no header | **401** |
| 9 | `Authorization: Something abc` | **401** |
| 10 | `Bearer this-is-not-a-jwt` | **401** |
| 11 | Expired JWT | **401** |
| 12 | Valid Bearer token | **200** matching email |
| 13 | PostgreSQL `password_hash` | starts with `$argon2`, not the plain password |

---

## 11. End-to-end walkthrough: register → login → document → job → SSE → result

```text
1. POST /api/v1/auth/register
   { "email": "...", "password": "StrongPassword123" }
        → 201  { id, email, created_at }

2. POST /api/v1/auth/login
   { "email": "...", "password": "StrongPassword123" }
        → 200  { access_token, token_type: "bearer" }

3. GET /api/v1/users/me
   Header: Authorization: Bearer <access_token>
        → 200  { id, email, created_at }

4. POST /api/v1/documents
   Header: Authorization: Bearer <access_token>
   { "title": "My first document", "content": "..." }
        → 201  { id, title, content, status, created_at, updated_at }

5. GET /api/v1/documents
   Header: Authorization: Bearer <access_token>
        → 200  [ { id, title, content, status, ... }, ... ]

6. GET /api/v1/documents/{document_id}
   Header: Authorization: Bearer <access_token>
        → 200  { id, title, content, status, ... }
        → 403 if another user's document
        → 404 if id not found

7. PATCH /api/v1/documents/{document_id}
   Header: Authorization: Bearer <access_token>
   { "title": "Updated title" }   (or "content", or both)
        → 200  updated DocumentResponse

8. DELETE /api/v1/documents/{document_id}
   Header: Authorization: Bearer <access_token>
        → 204  (empty body)

9. GET /api/v1/jobs/{job_id}
   Header: Authorization: Bearer <access_token>
        → 200  { id, document_id, status, created_at, started_at, completed_at }

10. GET /api/v1/documents/{document_id}/result
    Header: Authorization: Bearer <access_token>
        → 200  { word_count, character_count, ... }  (after job completes)

11. GET /api/v1/documents/{document_id}/events
    Header: Authorization: Bearer <access_token>
    # or: ?access_token=<jwt>  (for browser EventSource)
        → SSE stream: queued → processing → completed
        → 401 without token
```

Without a token, or with a bad/expired token, protected steps return **401**.

---

## 12. Hashing vs JWT (easy to mix up)

| | Password hash | JWT |
|---|----------------|-----|
| Purpose | Store login secret safely | Prove “this user already logged in” |
| Stored in DB? | Yes (`password_hash`) | No (client keeps the token) |
| Reversible? | No | Payload is readable; signature is not forgeable without the secret |
| Function pair | `hash_password` / `verify_password` | `create_access_token` / `decode_access_token` |

---

## 13. File map

| File | Role in the flows above |
|------|-------------------------|
| `.env` | Secrets and URLs |
| `app/core/config.py` | Load `.env` into `settings` |
| `app/main.py` | App + routers + exception handlers |
| `app/db/database.py` | Engine, `Base`, `get_db()` + rollback |
| `app/models/user.py` | `users` table |
| `app/models/document.py` | `documents` table |
| `app/models/processing_job.py` | `processing_jobs` table |
| `app/models/processing_result.py` | `processing_results` table |
| `app/schemas/user.py` | Register in/out |
| `app/schemas/auth.py` | Login in, token out |
| `app/schemas/document.py` | Document create/update/response |
| `app/schemas/job.py` | Job + result responses |
| `app/schemas/error.py` | `ErrorResponse` schema |
| `app/core/security.py` | Hash + JWT |
| `app/core/dependencies.py` | Bearer → User; ownership |
| `app/core/errors.py` | `error_type` constants |
| `app/core/exception_handlers.py` | Global error handlers |
| `app/api/v1/auth.py` | `/register`, `/login` |
| `app/api/v1/users.py` | `/users/me` |
| `app/api/v1/documents.py` | CRUD + SSE + result |
| `app/api/v1/jobs.py` | `GET /jobs/{job_id}` |
| `app/services/processing.py` | Async word/character count worker |
| `app/services/event_bus.py` | SSE pub/sub |
| `app/services/sse.py` | SSE stream helpers |
| `tests/conftest.py` | pytest fixtures + helpers |
| `tests/test_*.py` | 19 integration tests |
| `pytest.ini` | pytest config |
| `requirements-dev.txt` | pytest, pytest-asyncio, httpx |
| `alembic/env.py` | Migrations use same DB URL |
| `alembic/versions/...` | CREATE TABLE scripts |

**All roadmap steps complete (10/10).**

---

## 9. SSE / Server-Sent Events

Instead of polling `GET /jobs/{id}` in a loop, the client opens **one long-lived connection** and the server **pushes** status updates.

```http
GET /api/v1/documents/{document_id}/events
Authorization: Bearer <token>
# or for browser EventSource:
GET /api/v1/documents/{document_id}/events?access_token=<jwt>
Accept: text/event-stream
```

```text
Client opens SSE connection
        ↓
Snapshot from PostgreSQL (current status)
        ↓
Subscribe to in-memory event bus
        ↓
Background worker publishes:
  queued → processing → completed
        ↓
Each change pushed as SSE frame
        ↓
Stream closes on completed / failed
```

**Example frames:**

```text
event: status
data: {"document_id": "...", "status": "queued", "job_id": "..."}

event: status
data: {"document_id": "...", "status": "processing", "job_id": "..."}

event: status
data: {"document_id": "...", "status": "completed", "word_count": 5, "character_count": 26}
```

### Polling vs SSE

| Polling | SSE |
|---------|-----|
| Many `GET /jobs/{id}` requests | One `GET /documents/{id}/events` |
| Client pulls | Server pushes |
| Delay = poll interval | Near real-time |

### Architecture

| File | Role |
|------|------|
| `app/services/event_bus.py` | In-memory pub/sub per `document_id` |
| `app/services/sse.py` | Format SSE frames + stream generator |
| `app/services/processing.py` | Publishes events on status changes |
| `app/api/v1/documents.py` | `GET /documents/{id}/events` |
| `app/core/dependencies.py` | `get_current_user_sse` (header or `?access_token=`) |

### Test with curl

```bash
curl -N -H "Authorization: Bearer <token>" \
  http://127.0.0.1:8000/api/v1/documents/<document_id>/events
```

Create a document in another terminal first — you should see `queued`, `processing`, then `completed`.

**Step 9 complete.**

---

## 10. Testing + error handling

### 10.1 HTTPException + status codes

Routes and dependencies raise `HTTPException` with the correct status:

| Situation | Status | Example |
|-----------|--------|---------|
| Missing/invalid JWT | 401 | `get_current_user` |
| Wrong login | 401 | `POST /auth/login` |
| Resource not found | 404 | Document/job missing |
| Not owner | 403 | Another user's document |
| Duplicate email | 409 | `POST /auth/register` |
| Validation failed | 422 | Empty title, bad email |
| Created | 201 | Register, create document |
| Deleted | 204 | `DELETE /documents/{id}` |

### 10.2 Global exception handling

`app/core/exception_handlers.py` registers handlers on the FastAPI app:

```text
HTTPException          → JSON with error_type
RequestValidationError → 422 + validation_error
IntegrityError         → 409 conflict
SQLAlchemyError        → 500 database_error
Exception (catch-all)  → 500 internal_error
```

Registered in `app/main.py` via `register_exception_handlers(app)`.

### 10.3 Consistent error response shape

Every error returns:

```json
{
  "detail": "Document not found",
  "error_type": "not_found"
}
```

Validation errors:

```json
{
  "detail": [{"loc": ["body", "password"], "msg": "...", "type": "..."}],
  "error_type": "validation_error"
}
```

Schema: `app/schemas/error.py` (`ErrorResponse`).  
Error codes: `app/core/errors.py`.

### 10.4 Database rollback

`get_db()` in `app/db/database.py` rolls back on any exception before re-raising:

```python
async with AsyncSessionLocal() as session:
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
```

Routes still call `commit()` explicitly on success. Background worker (`process_document_job`) has its own try/except + rollback.

### 10.5 pytest setup

| File | Role |
|------|------|
| `pytest.ini` | `asyncio_mode = auto`, session event loop |
| `requirements-dev.txt` | `pytest`, `pytest-asyncio`, `httpx` |
| `tests/conftest.py` | `AsyncClient`, `auth_client`, helpers |

Run tests:

```bash
pip install -r requirements-dev.txt
pytest -v
```

Tests use the real PostgreSQL database from `.env`. `PYTEST_RUNNING=1` enables `NullPool` to avoid asyncpg loop issues.

### 10.6–10.9 Test modules

| File | Covers |
|------|--------|
| `tests/test_api.py` | `/`, `/health` |
| `tests/test_auth.py` | Register, login, `/users/me`, invalid token |
| `tests/test_errors.py` | Status codes, `error_type`, 403/404/409/422 |
| `tests/test_documents.py` | CRUD, isolation, processing job + result |
| `tests/test_sse.py` | Auth, completed snapshot, `?access_token=` |

### 10.10 Final test run

```bash
pytest -v
# 19 passed
```

**Step 10 complete. Roadmap finished (10/10).**

---
