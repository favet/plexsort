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

### 2026-06-27 - Mobile Public UI and Missing Coverage View

Tightened the public mobile UI after reviewing phone screenshots:

- Public filters now collapse automatically on mobile instead of taking the full first screen.
- Library stats remain compact in a three-column strip on mobile.
- Movie table rows become mobile cards below 700px instead of a horizontally clipped table.
- Added a first-class `Missing From Plex` section on the public page.
- Selecting a Letterboxd list now renders the `lb_only` entries from
  `GET /api/lists/{id}/compare`, which is the list of titles on Letterboxd but not in Plex.
- The missing section is visible as a prompt even before a list is selected.

Current live coverage gaps:

- `1 Million Club`: 489 in Plex, 291 missing, 62.69% coverage.
- `Movies on Plex`: 1,340 in Plex, 66 missing, 95.31% coverage.

Validation:

- Static assets copied to `C:\website\plexsort`.
- Public `GET /` returned `200`.
- Live page HTML contains `Missing From Plex`.
- Browser/mobile automation was attempted again, but the in-app browser timed out and reset,
  so visual verification is still not counted as passed.

### 2026-06-27 - Posters, Health Metrics, and Open Admin

Added public enrichment/readout features:

- `GET /api/posters/{plex_rating_key}` proxies Plex poster images through the backend.
  The Plex token is used server-side only and is not sent to the browser.
- Public movie rows now render Plex posters when `thumb_url` is present.
- `GET /api/health/metrics` returns library counts, match counts, match rate,
  confidence buckets, review queue counts, and per-list coverage.
- Public top-right gear opens a health metrics readout.
- Removed Caddy Basic Auth for `/admin*` and `/api/admin*` by user decision. The site,
  admin UI, and admin APIs are intentionally fully public.

Current live health metrics after deployment:

- Movies: 1,781
- Watched: 196
- Letterboxd entries: 2,186
- Matched entries: 1,829
- Unmatched entries: 357
- Match rate: 83.67%
- Confidence buckets: 0 high, 1,829 medium, 0 low, 357 none
- Pending review: 357
- Reviewed matches: 0
- `1 Million Club`: 489 in Plex, 291 missing, 62.69% coverage
- `Movies on Plex`: 1,340 in Plex, 66 missing, 95.31% coverage

Data provenance notes:

- Genres come from Plex API `Genre` tags collected during Plex sync.
- Posters come from Plex `thumb` paths, proxied via the backend.
- Best next enrichment path is TMDB: stable external IDs, posters/backdrops if desired,
  cast/crew, release dates, runtime normalization, and better matching.

### 2026-06-28 - OMDb Quota Handling

Diagnosed OMDb enrichment appearing stuck at 856 enriched movies:

- Live OMDb response for the next queued movie returned `Request limit reached!`.
- The existing enrichment job treated every failed OMDb response as a normal movie failure
  and did not record attempts, so repeated jobs retried the same first batch.
- Added Alembic revision `005_omdb_attempts` with `omdb_checked_at` and `omdb_error`.
- Permanent per-movie OMDb misses are now skipped so they do not pin the queue.
- OMDb request-limit responses now stop the batch without marking movies as failed or
  skipped, so the queue remains retryable after the quota resets.
- Admin OMDb status now reports `skipped` separately from `enriched` and `remaining`.
- Admin job toast now says when the OMDb request limit is reached.

Live state after deployment:

- With IMDb ID: 1,766
- Enriched: 856
- Skipped: 0
- Remaining: 910
- A one-item live enrichment verification returned `rate_limited: true`, `failed: 0`,
  `skipped: 0`, and left remaining at 910.

## Decisions Made

- Use Python 3.11+ with FastAPI.
- Use SQLAlchemy 2.x and Alembic.
- Use a dedicated Postgres container for PlexSort.
- Do not expose Postgres to the host.
- Keep public and admin surfaces open without Caddy auth by user decision on 2026-06-27.
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
- Caddy intentionally does not protect `/admin*` or `/api/admin*`.
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
| Public mobile UI | Improved | Filters collapse; movie rows become cards; stats stay compact. |
| Missing coverage view | Done, first pass | Public UI shows Letterboxd titles missing from Plex. |
| Poster proxy | Done, first pass | Public proxy serves Plex posters without exposing token. |
| Health metrics | Done, first pass | Gear readout uses `/api/health/metrics`. |
| Auth | Open | Public and admin routes intentionally require no auth. |
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
- `docker compose build app` passed.
- `docker compose up -d app` restarted the rebuilt backend.
- Updated static frontend assets were copied to `C:\website\plexsort`.
- Local `GET /health` returned `{"status":"ok"}`.
- Local selected-column CSV export returned `Title`, `IMDb Rating`, and `Country`.
- Caddy-facing selected-column CSV export returned real enriched rows.
- Caddy-facing `GET /api/stats` returned 1,781 movies, 196 watched, and 2 lists.
- Caddy-facing HTML references `assets/style.css?v=16`, `assets/app.js?v=16`, and includes
  the `exportAllLink` markup.
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
- `python -m ruff check .` passed after the mobile public UI changes.
- `python -m compileall src alembic tests` passed after the mobile public UI changes.
- `python -m pytest` passed with 13 tests after the mobile public UI changes.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues after the mobile public UI changes.
- `node --check frontend\assets\app.js` passed after the mobile public UI changes.
- `node --check frontend\assets\admin.js` passed after the mobile public UI changes.
- Public `https://plex.favet.net/` returned `200` after the mobile public UI changes.
- Public compare checks returned the current missing counts for both imported lists.
- `python -m ruff check .` passed after poster/health/open-admin changes.
- `python -m compileall src alembic tests` passed after poster/health/open-admin changes.
- `python -m pytest` passed with 15 tests after poster/health/open-admin changes.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues after poster/health/open-admin changes.
- `node --check frontend\assets\app.js` passed after poster/health/open-admin changes.
- `node --check frontend\assets\admin.js` passed after poster/health/open-admin changes.
- `docker compose build app` passed after poster/health/open-admin changes.
- `docker compose up -d app` restarted the rebuilt app container.
- `caddy validate --config C:\Users\Justin\.cloudflared\Caddyfile` passed.
- `caddy reload --config C:\Users\Justin\.cloudflared\Caddyfile` passed.
- Public `https://plex.favet.net/api/health/metrics` returned live health metrics.
- Public `https://plex.favet.net/api/posters/132` returned `200 image/jpeg`.
- Public `https://plex.favet.net/admin` returned `200` with no credentials.
- Public `https://plex.favet.net/api/admin/jobs` returned `200` with no credentials.
- `python -m ruff check .` passed after OMDb quota handling changes.
- `python -m compileall src alembic tests` passed after OMDb quota handling changes.
- `python -m pytest` passed with 18 tests after OMDb quota handling changes.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues after OMDb quota handling changes.
- `node --check frontend\assets\admin.js` passed after OMDb quota handling changes.
- `node --check frontend\assets\app.js` passed after OMDb quota handling changes.
- `docker compose build app` passed after OMDb quota handling changes.
- `docker compose run --rm app alembic upgrade head` applied `005_omdb_attempts`.
- `docker compose up -d app` restarted the rebuilt app container.
- Local `GET /health` returned `{"status":"ok"}` after OMDb quota handling changes.
- Local `GET /api/admin/omdb/status` returned 1,766 with IMDb IDs, 856 enriched,
  0 skipped, and 910 remaining.
- Local one-item OMDb enrichment job returned `rate_limited: true` with no failed or
  skipped movies.

### 2026-06-28 - OMDb Full Payload Backfill

Added full OMDb response preservation:

- Added Alembic revision `006_omdb_payload` with `plex_movies.omdb_payload` as JSONB.
- OMDb enrichment now stores the complete response payload for every successful lookup,
  while continuing to populate the existing normalized display columns.
- OMDb status now treats a movie as enriched only when the full payload is present.

Live backfill result with the current OMDb key:

- Full payloads saved: 847
- Remaining full payloads: 919
- Skipped/errors: 0
- Job stopped on `rate_limited: true`; no remaining movies were marked failed or skipped.

Follow-up with final OMDb key:

- Initially received `Invalid API key!` for the remaining 919 rows; this exposed that
  key-level OMDb errors also needed to stop the batch rather than mark movie rows failed.
- Added fatal key-error handling and cleared the false `Invalid API key!` skips.
- After the key became usable, a one-item verification saved 1 payload.
- Final batch saved the remaining 918 payloads.
- Final OMDb full-payload status: 1,766 with IMDb IDs, 1,766 full payloads saved,
  0 skipped, 0 remaining.

### 2026-06-28 - OMDb Fields Exposed and Detail Drawer

Started the enriched data UI phase:

- Added safe computed public fields from `omdb_payload` without exposing the raw payload:
  - IMDb rating
  - rated
  - released
  - runtime
  - genre
  - writer
  - plot
  - language
  - country
  - poster
  - full OMDb ratings array
- Public movie API responses now include those fields while still excluding `omdb_payload`.
- Public movie detail drawer now groups data into overview, ratings, cast/crew, awards,
  and technical sections.
- Public movie table keeps a compact default layout but now stacks Plex, IMDb, and Rotten
  Tomatoes ratings in the ratings column when available.
- Updated and copied static frontend assets to `C:\website\plexsort`.

Validation:

- `python -m ruff check .` passed.
- `python -m compileall src alembic tests` passed.
- `python -m pytest` passed with 19 tests.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues.
- `node --check frontend\assets\app.js` passed.
- `node --check frontend\assets\admin.js` passed.
- `docker compose build app` passed.
- `docker compose up -d app` restarted the rebuilt backend.
- Live public API returned OMDb detail fields including `omdb_plot`.
- Live public HTML references `assets/style.css?v=13` and `assets/app.js?v=13`.

### 2026-06-28 - Desktop Column Presets

Added first-pass desktop column management:

- Public movie table headers and cells now render from a column definition map.
- Added a `Columns` control with presets:
  - library
  - ratings
  - release
  - technical
  - people
  - omdb
- Added checkbox column selection with `localStorage` persistence.
- The default table remains compact, while users can opt into wider enriched-data views.
- Non-sortable enriched columns render as plain headers; backend sort/filter expansion remains
  a later phase.
- Copied updated static frontend assets to `C:\website\plexsort`.

Validation:

- `python -m ruff check .` passed.
- `python -m compileall src alembic tests` passed.
- `python -m pytest` passed with 19 tests.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues.
- `node --check frontend\assets\app.js` passed.
- `node --check frontend\assets\admin.js` passed.
- Live public HTML references `assets/style.css?v=14`, `assets/app.js?v=14`, and includes
  the `columnPanel` markup.

### 2026-06-28 - Enriched Filters and Sorts

Added first-pass OMDb-powered filtering and sorting:

- Backend `/api/movies` now supports whitelisted enriched sorts:
  - `imdb_rating`
  - `metascore`
  - `released`
- Backend `/api/movies` and `/api/export/movies-csv` now support enriched filters:
  - `omdb_rated`
  - `country`
  - `language`
  - `min_imdb_rating`
  - `min_metascore`
- Public sidebar includes controls for those enriched filters.
- Public sort dropdown includes IMDb rating, Metascore, and Released.
- Export URLs include the new enriched filters.

Validation:

- `python -m ruff check .` passed.
- `python -m compileall src alembic tests` passed.
- `python -m pytest` passed with 19 tests.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues.
- `node --check frontend\assets\app.js` passed.
- `node --check frontend\assets\admin.js` passed.
- `docker compose build app` passed.
- `docker compose up -d app` restarted the rebuilt backend.
- Live API check for `country=France`, `min_imdb_rating=7.5`, and `sort=imdb_rating`
  returned real enriched matches.
- Live HTML references `assets/style.css?v=15`, `assets/app.js?v=15`, and includes
  the new enriched filter controls.

### 2026-06-28 - Column-Aware Enriched CSV Exports

Finished the export part of the desktop column phase:

- `/api/export/movies-csv` now accepts a whitelisted repeated `columns` query parameter.
- `columns=all` exports the full safe enriched movie shape, including OMDb plot, release,
  ratings, cast/crew, country/language, and technical fields.
- The public page's `Export view` link now exports the currently visible column picker
  selection while preserving active filters and sort order.
- Added an `Export all data` link for the full safe enriched dataset.
- Raw `omdb_payload` remains internal-only and is not exported.

Validation:

- `python -m ruff check .` passed.
- `python -m compileall src alembic tests` passed.
- `python -m pytest` passed with 20 tests.
- `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort` passed with
  no issues.
- `node --check frontend\assets\app.js` passed.
- `node --check frontend\assets\admin.js` passed.

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
- Add browser-level public mobile UI verification once browser automation is responsive.
