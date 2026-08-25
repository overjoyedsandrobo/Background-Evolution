# Background Evolution

A small desktop game: hatch a monster, then combine environments to evolve
new ones and unlock more of the world.

## Architecture

This is a client/server app, local-only (no auth, no hosted deployment):

- **`backend/`** — a FastAPI service that owns all game logic (the
  environment-combination engine) and persistence (Postgres via SQLAlchemy +
  Alembic). Runs in Docker.
- **`client/`** — the pygame desktop app. Renders the UI and talks to the
  backend over local HTTP. Runs natively (not in Docker — it's a Windows GUI
  app with taskbar/tray integration that can't run headless in a container).

The client is "dumb": it sends state (time elapsed, which environment is
selected) to the backend and renders whatever the backend says is true. The
backend decides things like when a new environment unlocks.

## Running it

**1. Start the backend + database:**

```
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.yml --env-file docker/.env up
```

This builds the backend image, brings up Postgres, runs migrations, and
starts the API on `http://127.0.0.1:8000`.

**2. Run the client** (Windows, needs its own environment — see Development
setup below):

```
cd client
poetry run python main.py
```

It looks for the backend at `http://127.0.0.1:8000` by default; override with
the `BACKEND_BASE_URL` environment variable if you're pointing it elsewhere.

## Development setup

Both `backend/` and `client/` are managed with [Poetry](https://python-poetry.org/)
(`pip install poetry`), each with its own `pyproject.toml`/`poetry.lock` since
their dependencies barely overlap (FastAPI/SQLAlchemy vs pygame/pystray) and
they deploy differently (backend → Docker image, client → native script).
`poetry.toml` in each pins the venv to `.venv/` inside that directory.

Backend:
```
cd backend
poetry install --with test
```

Client:
```
cd client
poetry install --with test
```

Both use `ruff` for linting/formatting (config at the repo root, `ruff.toml`):
```
ruff check backend client
ruff format backend client
```

## Running tests

Backend tests need a real Postgres (not SQLite — the schema and constraints
are Postgres-specific). Point `TEST_DATABASE_URL` at one, e.g. the `db`
service from `docker compose` above, or a second local Postgres instance:
```
cd backend
set TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/background_evolution_test
poetry run pytest tests/
```

Client tests are pure-logic (UI helpers, layout geometry, the API client's
request/response handling) and don't need a display or a running backend:
```
cd client
poetry run pytest tests/
```

## Database migrations

New schema changes go through Alembic:
```
cd backend
poetry run alembic revision --autogenerate -m "describe the change"
poetry run alembic upgrade head
```

## Notes

- Local save data used to live in `saves/save_slots.json`. That's gone —
  Postgres is now the only source of truth for game state. Nothing in this
  repo reads or writes that file anymore.
- No authentication or multi-user support: this assumes one player running
  the backend on their own machine. It isn't designed to be exposed to a
  network beyond `localhost`.
