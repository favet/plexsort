# PlexSort Status Log

This file is the running project memory. Update it at every meaningful checkpoint before
moving on to the next phase.

## Current Snapshot

- Date: 2026-06-27
- Workspace: `C:\Users\Justin\Documents\PLEXSORT`
- Public hostname target: `plex.favet.net`
- Backend target port: `8004`
- Static frontend target: `C:\website\plexsort`
- Current stage: backend foundation complete; frontend and real data sync not started.

## What Happened

### 2026-06-27 - Backend Foundation

Created the initial FastAPI backend scaffold:

- Python package under `src/plexsort`
- FastAPI app entrypoint at `src/plexsort/main.py`
- Dockerfile and Docker Compose app/db services
- Optional `.env` support with `.env.example`
- SQLAlchemy models for:
  - `plex_movies`
  - `lb_lists`
  - `lb_entries`
  - `matches`
- Alembic configuration and initial migration
- Public API route module
- Admin API route module
- Plex API ingestion module
- Letterboxd CSV/zip import module
- Letterboxd URL scrape module
- Title/year matching engine
- Public response schemas that explicitly list safe fields
- `.gitignore` for secrets and tool caches

Fixed an important auth documentation issue:

- Admin page and admin API must both be protected by Caddy.
- Correct matcher is `@admin path /admin* /api/admin*`.
- The earlier `/admin*`-only matcher would have left `/api/admin*` exposed.

Added initial tests:

- Matching normalization and confidence behavior
- Public movie schema field allowlist

The first test run caught a real normalization bug: accented leading words such as
`À bout de souffle` were being treated like the English article `A` after accent folding.
The matching normalizer now strips English articles before removing accent marks.

## Decisions Made

- Use Python 3.11+ with FastAPI.
- Use SQLAlchemy 2.x and Alembic.
- Use a dedicated Postgres container for PlexSort.
- Do not expose Postgres to the host.
- Use Caddy HTTP Basic Auth for `/admin*` and `/api/admin*`.
- Keep public browse/API open.
- Store secrets only in `.env`; never commit `.env`.
- Ingest Plex through the Plex HTTP API only.
- Never read Plex internal SQLite.
- Ingest Letterboxd via public page scrape or exported CSV/zip only.
- Do not use a Letterboxd API.
- Keep TMDB integration out of the first version.
- Treat safe public serialization as a hard boundary.

## Security Invariants

These must remain true after every checkpoint:

- Public API responses must not include filesystem paths.
- Public API responses must not include internal hostnames.
- Public routes must not expose arbitrary SQL or arbitrary model fields.
- Admin mutation routes must live under `/api/admin`.
- Caddy must protect both `/admin*` and `/api/admin*` before public deployment.
- Plex token must never appear in source control, logs, frontend code, or public responses.

## Implementation Status

| Area | Status | Notes |
|---|---|---|
| Backend scaffold | Done | App imports and route modules exist. |
| Docker Compose | Done | App + dedicated Postgres. `.env` is optional for config validation. |
| Database schema | Done, first pass | Migration exists. Needs live migration test against Postgres. |
| Public API | Done, first pass | Query filters and safe schemas exist. Needs integration tests. |
| Admin API | Done, first pass | Currently synchronous job execution. Async/background jobs can come later. |
| Plex ingestion | First pass | Needs real Plex credentials and pagination hardening. |
| Letterboxd CSV import | First pass | Needs tests with real export shapes. |
| Letterboxd scrape | First pass | Needs live scrape test and better retry/backoff behavior. |
| Matching engine | First pass | Title/year matching exists. TMDB deferred. |
| Frontend | Not started | Target is `C:\website\plexsort`. |
| Infra wiring | Not started | Caddy/cloudflared edits still pending. |
| Real data sync | Partially unblocked | `PLEX_URL` and `PLEX_LIBRARY=Movies` are recorded in `.env`; actual `PLEX_TOKEN` value still needed. |

## Plex Environment Status

Received on 2026-06-27:

- `PLEX_URL` is the HTTPS `plex.direct` local server URL ending in port `32400`.
- `PLEX_LIBRARY` is `Movies`.
- `PLEX_LIBRARY` means the Plex library section title inside Plex, not a filesystem folder.
- `.env` has been created with the URL and library.
- `PLEX_TOKEN` still contains a placeholder because the provided text appeared to be an instruction,
  not the actual token value.

## Git Status

Initialized local git repository on 2026-06-27.

- Branch: `main`
- Public remote repository: `https://github.com/favet/plexsort`
- `.env` is ignored and must not be committed.
- Initial commit `7c652b7` includes docs, backend scaffold, migration, and tests.
- `main` is pushed to `origin/main`.

## Validation So Far

- `python -m ruff check .` passed.
- `python -m compileall src alembic` passed.
- `python -m compileall src alembic tests` passed.
- `python -m pytest` passed with 5 tests.
- `docker compose config` passed.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` was attempted.
  It reached real type checking once cache permissions were fixed, but local installed packages/stubs
  were incomplete. Expected fix: install project dev dependencies with `pip install -e .[dev]`.

## Known Gaps

- No live Postgres migration has been run yet.
- No Docker image build has been run yet.
- No API integration tests exist yet.
- No frontend exists yet.
- Plex sync has not been tested against a real server.
- Letterboxd scrape has not been tested against a real public list.
- Admin API currently runs long work inline rather than as a background job queue.
- Plex library sync does not yet handle paginated library results robustly.

## Next Checkpoint

Recommended next checkpoint: backend verification against Docker Postgres.

Exit criteria:

- Docker image builds.
- Containers start.
- Alembic migration applies.
- `/health` returns `{"status":"ok"}`.
- Public API endpoints return safe empty responses before data sync.
- Initial unit tests pass.
