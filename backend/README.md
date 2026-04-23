# Lap Coach backend — FastAPI + Postgres

Self-hosted replacement for the Supabase Connected v1 design. Same wire
contract with the desktop; different plumbing.

## Layout

```
backend/
├── app/
│   ├── main.py            # app factory, routers, error handlers
│   ├── config.py          # typed env var loader
│   ├── database.py        # async engine + session factory
│   ├── models.py          # SQLAlchemy ORM (7 tables)
│   ├── schemas.py         # Pydantic request/response models
│   ├── auth.py            # device-token + JWT-cookie dependencies
│   ├── envelope.py        # idempotency helpers + UUIDv5 derivation
│   └── routers/
│       ├── ingest.py      # POST /sessions-start, /sessions-end, /laps-batch, /coaching-batch, /events-batch
│       ├── auth_routes.py # POST /auth/login, /auth/logout, GET /auth/me
│       └── read.py        # GET /sessions, /sessions/{id}
├── alembic/               # migrations (0001_connected_v1 creates everything)
├── scripts/create_user.py # CLI: mint user + device token
├── tests/                 # pytest-asyncio
├── Dockerfile
└── docker-compose.yml
```

## Quick start

```bash
cd backend
cp .env.example .env
# Generate SECRET_KEY:
python -c "import secrets; print(secrets.token_hex(32))"  # paste into .env

# Bring up Postgres + API in Docker:
docker-compose up -d

# Create the first user + device token:
docker-compose exec api python -m scripts.create_user alice@example.com --label "my laptop"
# Password: ****
# Confirm : ****
# device_token: <copy this into the desktop Settings panel>

# Health check:
curl http://localhost:8000/health
# {"ok":true}
```

## Deploy on a host without Docker

```bash
python -m pip install -e ".[dev]"
export DATABASE_URL="postgresql+asyncpg://user:pw@host/db"
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Contract

All five ingest endpoints share this shape:

- `Authorization: Bearer <device_token>` — or 401 `{"ok":false,"code":"auth_failed"}`
- `Idempotency-Key: <UUID>` — or 400 `{"ok":false,"code":"missing_envelope_id"}`
- Pydantic validation — 400 `{"ok":false,"code":"invalid_payload","message":"...","field":"..."}`
- Success — 200 `{"ok":true,"envelope_id":"...","already_seen":false}`
- Replay — 200 `{"ok":true,"envelope_id":"...","already_seen":true}`
- Missing parent session — 409 `{"ok":false,"code":"missing_session"}`

Webapp auth:

- `POST /auth/login` `{email, password}` → sets `lc_session` HttpOnly cookie, returns `UserOut`
- `POST /auth/logout` → clears cookie
- `GET  /auth/me` → current `UserOut`, 401 if no cookie

Read endpoints for the webapp (require session cookie):

- `GET /sessions?limit=100` → array of `SessionSummary`
- `GET /sessions/{session_id}` → full `SessionDetail` (summary + laps + coaching + events + envelope count)

## Authorisation model

No Postgres RLS. Every query in `routers/read.py` filters by
`user.id` from the authenticated session cookie, and every ingest
insert sets `user_id` from the device-token lookup. A test in
`tests/test_isolation.py` proves cross-user reads are impossible.

## Known limitations

- Single-user-per-device. Reassigning a device to a different user
  requires SQL-level `UPDATE devices SET user_id = ...`.
- No refresh tokens. Session JWT valid for `SESSION_TTL_HOURS` (default
  30 days) then user re-logs.
- No password reset flow. Admin resets via `scripts/create_user.py`
  (will fail if user exists — delete and recreate).
- Rate limiting is enforced only by Pydantic batch size caps (200).
  Global per-IP / per-user limits deferred.
- No OpenAPI type generation for the webapp yet; webapp hand-maintains
  its type mirror.
