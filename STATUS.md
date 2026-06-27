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
- `.dockerignore` so `.env` and cache folders are not sent to Docker build context

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

### 2026-06-27 - Static Frontend First Pass

Created a tracked static frontend under `frontend/` and deployed a copy to
`C:\website\plexsort`.

Created:

- `frontend/index.html`
- `frontend/admin.html`
- `frontend/assets/style.css`
- `frontend/assets/app.js`
- `frontend/assets/admin.js`

The public page includes:

- Filter sidebar
- Stats strip
- Sortable movie table
- Pagination controls
- Letterboxd list selector and coverage summary
- Empty state for pre-sync data

The admin page includes:

- Backend/sync status
- Plex sync trigger
- Letterboxd URL scrape form
- Letterboxd CSV/zip upload form
- Match review queue
- Manual match run trigger

Added a narrow localhost-only CORS allowance for `http://localhost:8014` and
`http://127.0.0.1:8014` so the static frontend can be tested locally against
the Docker backend. Production through Caddy remains same-origin.

### 2026-06-27 - Public Launch and Job Progress

Published PlexSort at `https://plex.favet.net`.

Public verification:

- `GET /` returns the static frontend through Cloudflare/Caddy.
- `GET /api/stats` returns public library counts.
- `GET /admin` returns `401 Unauthorized`.
- `GET /api/admin/sync/status` returns `401 Unauthorized` without Basic Auth.

Added durable job progress tracking:

- New `job_runs` table via Alembic revision `002_job_runs`
- `GET /api/admin/jobs`
- `GET /api/admin/jobs/{job_id}`
- `POST /api/admin/sync/plex` now queues a background job
- `POST /api/admin/lists/scrape` now queues a background job
- `POST /api/admin/lists/upload` now queues a background job
- `POST /api/admin/match/run` now queues a background job
- Admin UI polls job progress and shows phase/current/total

Verified with a real match job:

- Queued job `915a8bff-40be-4d23-babf-aa2bb7a40fe8`
- Progress reported from `1 / 2186` through `2186 / 2186`
- Final status: `completed`
- Result: `matched_count = 2186`

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
| Database schema | Done, first pass | Migration applies cleanly to Docker Postgres. |
| Public API | Done, first pass | Query filters and safe schemas exist. Needs integration tests. |
| Plex ingestion | First pass | Needs real Plex credentials and pagination hardening. |
| Letterboxd CSV import | First pass | Needs tests with real export shapes. |
| Letterboxd scrape | First pass | Needs live scrape test and better retry/backoff behavior. |
| Matching engine | First pass | Title/year matching exists. TMDB deferred. |
| Admin API | Progress-enabled | Admin mutations now queue background jobs with status records. |
| Frontend | First pass | Tracked under `frontend/`; deployed to `C:\website\plexsort`. |
| Infra wiring | Live | `plex.favet.net` routes through Cloudflare Tunnel to Caddy and backend. |
| Real data sync | Done, first pass | Plex synced 1,781 movies; two Letterboxd CSV lists imported. |

## Plex Environment Status

Received on 2026-06-27:

- `PLEX_URL` is the HTTPS `plex.direct` local server URL ending in port `32400`.
- `PLEX_LIBRARY` is `Movies`.
- `PLEX_LIBRARY` means the Plex library section title inside Plex, not a filesystem folder.
- `.env` has been created with the URL and library.
- `PLEX_TOKEN` is present in ignored local `.env`; never commit or print it.

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
- `node --check frontend\assets\app.js` passed.
- `node --check frontend\assets\admin.js` passed.
- `docker compose config` passed.
- `docker compose build` passed.
- `docker compose up -d` started app and database containers.
- `docker compose run --rm app alembic upgrade head` applied `001_initial_schema`.
- `docker compose run --rm app alembic current` reported `001_initial_schema (head)`.
- `docker compose run --rm app alembic current` later reported `002_job_runs (head)`.
- Docker Postgres contains expected tables: `alembic_version`, `plex_movies`, `lb_lists`,
  `lb_entries`, and `matches`.
- Live `GET /health` returned `{"status":"ok"}`.
- Live `GET /api/stats` returned empty counts.
- Live `GET /api/movies?per_page=5` returned an empty safe page.
- Live `GET /api/lists` returned `[]`.
- Browser verification against `http://localhost:8014/` showed public page rendering with
  empty live API data, no console errors, and no page-level horizontal overflow.
- Browser verification against `http://localhost:8014/admin.html` showed admin page rendering
  with backend status online, no review items, no console errors, and no page-level horizontal overflow.
- Mobile viewport check at 390px wide showed no page-level horizontal overflow; the movie table
  scrolls inside its own frame.
- Public `https://plex.favet.net/api/stats` returned `1781` movies, `196` watched, `2` lists.
- Public admin job endpoint returned `401` without Basic Auth.
- Public admin job endpoint returned the completed match job with Basic Auth.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` was attempted.
  It reached real type checking once cache permissions were fixed, but local installed packages/stubs
  were incomplete. Expected fix: install project dev dependencies with `pip install -e .[dev]`.

## Known Gaps

- No API integration tests exist yet.
- Letterboxd scrape has not been tested against a real public list.
- Plex library sync does not yet handle paginated library results robustly.

## Next Checkpoint

Recommended next checkpoint: improve matching quality and add API integration tests.

Exit criteria:

- API integration tests exercise `/health`, `/api/stats`, `/api/movies`, and `/api/lists`
  against an isolated test database or controlled dependency override.
- Add integration tests for job creation/status.
- Add admin review tooling for the 357 currently unmatched entries.
