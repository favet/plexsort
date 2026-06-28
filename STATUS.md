# PlexSort Status Log

This file is the running project memory. Update it at every meaningful checkpoint before
moving on to the next phase.

## Current Snapshot

- Date: 2026-06-27
- Workspace: `C:\Users\Justin\Documents\PLEXSORT`
- Public hostname target: `plex.favet.net`
- Backend target port: `8004`
- Static frontend target: `C:\website\plexsort`
- Current stage: public site live with real Plex data, imported Letterboxd lists,
  progress-tracked admin jobs, and first-pass manual match review tools.

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

### 2026-06-27 - Admin Review Workflow

Added first-pass tools for working through unmatched/low-confidence matches:

- `GET /api/admin/movies/search?q=...&limit=...` searches Plex movies for manual
  review candidates. This endpoint is admin-only through Caddy and includes the
  internal PlexSort movie row ID needed for safe manual assignment.
- `GET /api/admin/matches/review` now accepts `limit` and defaults to 50 items.
- Admin UI review cards now include:
  - editable Plex search query
  - candidate search results
  - one-click manual match confirmation
  - skip/mark-unmatched action
- Manual confirmations call `PATCH /api/admin/matches/{id}` with
  `match_method = manual`; skips use `match_method = manual_unmatched`.

Deployed the updated backend container and copied updated static frontend assets to
`C:\website\plexsort`.

Live data snapshot after deployment:

- Plex movies: 1,781
- Watched movies: 196
- Letterboxd lists: 2
- Match counts: 1,829 medium, 357 none
- Current review queue: 357

### 2026-06-27 - API Integration Tests and Type Gate

Added route-level API integration tests with an isolated in-memory SQLite database:

- Public health/stats/movie/list/compare responses
- Public movie response field allowlist
- Admin movie search response shape
- Admin match review search/confirm workflow
- Admin job list/status reads

To make these tests possible without Postgres, model columns now keep Postgres
`ARRAY`/`JSONB` behavior in production and use SQLite-compatible JSON variants in
test databases.

Installed local dev extras with `python -m pip install -e .[dev]` so host tests use
the declared project dependency set. After that, fixed the remaining `mypy` source
error by renaming a shadowed local variable in the Letterboxd CSV importer.

Rebuilt and restarted the Docker app container after the source changes. Public
verification remained healthy:

- Local `GET /health`: `{"status":"ok"}`
- Public `GET /api/stats`: `1781` movies, `196` watched, `2` lists
- Public unauthenticated `GET /api/admin/jobs`: `401`

### 2026-06-27 - Plex Pagination and Path-Stripping Tests

Hardened Plex ingestion:

- Plex library sync now requests movies in pages using `X-Plex-Container-Start`
  and `X-Plex-Container-Size`.
- Sync follows `totalSize` until all listing pages have been collected.
- Added tests with fake Plex XML covering:
  - library section lookup
  - two-page library listing
  - per-movie metadata fetches
  - media `Part file="..."` paths returned by Plex
  - public schema output that excludes path-bearing fields

Rebuilt and restarted the Docker app container after this change.

### 2026-06-27 - Admin Review Counts and Filters

Improved review queue visibility:

- Added `GET /api/admin/matches/review/summary` with pending low, pending none,
  pending total, and reviewed counts.
- Added `confidence=all|low|none` filter support to `GET /api/admin/matches/review`.
- Admin matching panel now shows the review counts and segmented All/Low/None filters.
- Updated API integration tests to cover the summary endpoint and filtered review list.

Live verification after deploy:

- Public unauthenticated review summary endpoint returned `401`.
- Public authenticated review summary returned `357` pending, `0` low, `357` none,
  `0` reviewed.
- Public authenticated filtered review endpoint returned unmatched review items for
  `confidence=none`.
- Browser smoke was attempted, but the browser automation timed out while waiting for page
  load state, so it is not counted as a passed validation checkpoint.

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
| Plex ingestion | Improved | Real sync works; pagination and path stripping now have tests. |
| Letterboxd CSV import | First pass | Needs tests with real export shapes. |
| Letterboxd scrape | First pass | Needs live scrape test and better retry/backoff behavior. |
| Matching engine | First pass | Title/year matching exists. TMDB deferred. |
| Admin API | Progress-enabled | Admin mutations now queue background jobs with status records. |
| Admin review | First pass | Search, confirm, and skip tools exist for the review queue. |
| Admin review filters | Done, first pass | Counts and All/Low/None filters are live. |
| API tests | Improved | Public/admin route tests now cover core response shapes and manual review. |
| Type checking | Passing | `mypy` is green after installing dev extras. |
| Frontend | First pass live | Tracked under `frontend/`; deployed to `C:\website\plexsort`. |
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
- Local `GET /health` returned `{"status":"ok"}` after rebuilding the app image.
- Local Caddy `GET /api/admin/movies/search?q=12%20Monkeys&limit=3` returned the
  expected Plex candidate with Basic Auth.
- Local Caddy `GET /api/admin/movies/search?q=x` returned `401` without Basic Auth.
- Local Caddy `GET /api/admin/matches/review?limit=2` returned two review items
  with Basic Auth.
- Public `https://plex.favet.net/` returned `200`.
- Public `https://plex.favet.net/api/stats` returned `1781` movies, `196` watched,
  `2` lists.
- Public `https://plex.favet.net/api/admin/movies/search?q=x` returned `401`
  without Basic Auth.
- Public `https://plex.favet.net/api/admin/movies/search?q=12%20Monkeys&limit=1`
  returned the expected Plex candidate with Basic Auth.
- `python -m ruff check .` passed after the admin review workflow.
- `python -m compileall src alembic tests` passed after the admin review workflow.
- `python -m pytest` passed with 8 tests after the admin review workflow.
- `node --check frontend\assets\admin.js` passed after the admin review workflow.
- `python -m pip install -e .[dev]` installed missing host dev/runtime dependencies.
- `python -m ruff check .` passed after API integration tests were added.
- `python -m compileall src alembic tests` passed after API integration tests were added.
- `python -m pytest` passed with 11 tests after API integration tests were added.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues after API integration tests were added.
- `node --check frontend\assets\app.js` passed after API integration tests were added.
- `node --check frontend\assets\admin.js` passed after API integration tests were added.
- `docker compose build app` passed after source changes.
- `docker compose up -d app` restarted the rebuilt app container.
- Live `GET /health` returned `{"status":"ok"}` after the rebuild.
- Public `https://plex.favet.net/api/stats` returned `1781` movies, `196` watched,
  `2` lists after the rebuild.
- Public `https://plex.favet.net/api/admin/jobs` returned `401` without Basic Auth
  after the rebuild.
- `python -m ruff check .` passed after Plex ingestion pagination tests were added.
- `python -m compileall src alembic tests` passed after Plex ingestion pagination tests were added.
- `python -m pytest` passed with 13 tests after Plex ingestion pagination tests were added.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues after Plex ingestion pagination tests were added.
- `node --check frontend\assets\app.js` passed after Plex ingestion pagination tests were added.
- `node --check frontend\assets\admin.js` passed after Plex ingestion pagination tests were added.
- `docker compose build app` passed after Plex ingestion pagination changes.
- `docker compose up -d app` restarted the rebuilt app container after Plex ingestion
  pagination changes.
- `python -m ruff check .` passed after admin review filters were added.
- `python -m compileall src alembic tests` passed after admin review filters were added.
- `python -m pytest` passed with 13 tests after admin review filters were added.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues after admin review filters were added.
- `node --check frontend\assets\app.js` passed after admin review filters were added.
- `node --check frontend\assets\admin.js` passed after admin review filters were added.
- `docker compose build app` passed after admin review filter changes.
- `docker compose up -d app` restarted the rebuilt app container after admin review
  filter changes.
- Updated static admin assets were copied to `C:\website\plexsort`.

## Known Gaps

- No API integration tests exist yet.
- Letterboxd scrape has not been tested against a real public list.
- Plex library sync does not yet handle paginated library results robustly.

## Next Checkpoint

Recommended next checkpoint: harden matching quality and admin review ergonomics.

Exit criteria:

- Improve match confidence quality beyond title/year matching, likely by adding TMDB ID support
  once a TMDB API key is available.
- Add safer bulk workflow controls for the review queue.
- Add browser-level admin UI verification once browser automation is responsive.
