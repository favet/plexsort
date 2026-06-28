# PlexSort Implementation Plan

Read CLAUDE.md first for all stack/infra decisions. This file is the phase-by-phase build order for the next coding session(s).

---

## Current project status

See `STATUS.md` for the running work log and `TESTING.md` for required checkpoint gates.

As of 2026-06-27:

- Backend foundation is scaffolded.
- Initial schema, API modules, ingestion modules, and matching module exist.
- Initial unit tests exist.
- Frontend first pass exists and is deployed to `C:\website\plexsort`.
- Infra is live at `https://plex.favet.net`.
- Real Plex sync completed: 1,781 movies.
- Two Letterboxd CSV lists are imported.
- Admin long-running actions now create progress-tracked jobs.
- Admin review has first-pass manual tools: search Plex movies, confirm a match,
  or mark an entry unmatched.
- Public route `https://plex.favet.net` is verified live; admin routes are intentionally
  open with no Basic Auth.
- API integration tests now cover core public/admin route shapes.
- `mypy` is green after installing declared dev dependencies.
- Plex ingestion now has pagination support plus tests proving Plex `Part file`
  paths are ignored.
- Admin review now shows pending/reviewed counts and All/Low/None filters.
- Public mobile UI now collapses filters and renders movies as cards.
- Public list comparison now exposes `Missing From Plex` as the main coverage gap view.
- Public poster proxy and health metrics endpoints are live.

---

## Phase 1 — Scaffold ✅ (complete)

- [x] Decisions locked: Python/FastAPI, Docker compose, own Postgres, public browse/admin, no TMDB key yet
- [x] CLAUDE.md written
- [x] Project directory created at `C:\Users\Justin\Documents\PLEXSORT\`
- [x] Memory saved (see `C:\Users\Justin\.claude\projects\c--website-plexsort\memory\`)

---

## Phase 2 — Project skeleton ✅ (complete)

Created the following structure:

```
PLEXSORT/
├── CLAUDE.md           (exists)
├── PLAN.md             (this file)
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
└── src/
    └── plexsort/
        ├── __init__.py
        ├── main.py           # FastAPI app entrypoint
        ├── db.py             # SQLAlchemy engine/session
        ├── models.py         # ORM models
        ├── config.py         # pydantic Settings from env
        ├── api/
        │   ├── __init__.py
        │   ├── public.py     # public routes (browse, compare)
        │   └── admin.py      # admin routes (sync triggers, list upload, match review)
        ├── ingest/
        │   ├── __init__.py
        │   ├── plex.py       # Plex API ingestion
        │   ├── lb_scrape.py  # Letterboxd URL scraper
        │   └── lb_csv.py     # Letterboxd CSV/zip parser
        └── match/
            ├── __init__.py
            └── engine.py     # title+year matching, confidence scoring
```

And in `C:\website\plexsort\`:
```

Frontend files are still pending; backend files are complete for the first scaffold checkpoint.
index.html          # public browse SPA (vanilla JS)
admin.html          # admin UI (public)
assets/
    app.js
    style.css
```

---

## Phase 3 — Postgres schema ✅ (first pass complete)

Three core tables + join table:

### `plex_movies`
| Column | Type | Notes |
|---|---|---|
| id | serial PK | |
| plex_rating_key | text UNIQUE | Plex's internal movie ID |
| title | text NOT NULL | |
| title_sort | text | Plex's sortable title |
| year | int | |
| tmdb_id | text | from Plex guid when present |
| imdb_id | text | from Plex guid when present |
| genres | text[] | |
| directors | text[] | |
| duration_ms | bigint | runtime |
| resolution | text | e.g. "1080p", "4K" |
| video_codec | text | |
| audience_rating | numeric | Plex/RT audience rating |
| rating | numeric | Plex/critic rating |
| content_rating | text | e.g. "R", "PG-13" |
| studio | text | |
| summary | text | |
| thumb_url | text | poster path, public-safe Plex image URL |
| added_at | timestamptz | |
| last_viewed_at | timestamptz | nullable |
| view_count | int | |
| last_synced_at | timestamptz | when this row was last pulled |

**DO NOT include**: `file`, `file_path`, `media_path`, `library_section_path`, or any column exposing filesystem paths.

### `lb_entries`
| Column | Type | Notes |
|---|---|---|
| id | serial PK | |
| list_id | int FK → lb_lists | |
| title | text NOT NULL | as scraped/parsed |
| year | int | |
| lb_film_slug | text | e.g. "the-godfather" from URL |
| lb_film_url | text | full Letterboxd film URL |
| list_position | int | for ordered lists |
| lb_rating | numeric | from diary/ratings exports |
| lb_watched_date | date | from diary/watched exports |
| created_at | timestamptz | |

### `lb_lists`
| Column | Type | Notes |
|---|---|---|
| id | serial PK | |
| name | text NOT NULL | |
| source_type | text | 'url_scrape' / 'csv_export' |
| source_url | text | nullable (for scrape source) |
| list_kind | text | 'watchlist' / 'watched' / 'diary' / 'ratings' / 'list' |
| last_updated_at | timestamptz | |
| entry_count | int | |

### `matches`
| Column | Type | Notes |
|---|---|---|
| id | serial PK | |
| lb_entry_id | int FK → lb_entries | |
| plex_movie_id | int FK → plex_movies | nullable (NULL = unmatched) |
| confidence | text | 'high' / 'medium' / 'low' / 'none' |
| match_method | text | 'tmdb_id' / 'exact_title_year' / 'fuzzy_title_year' |
| matched_at | timestamptz | |
| reviewed | bool DEFAULT false | admin-reviewed flag |
| reviewer_note | text | nullable |

**Indexes needed**: plex_movies(year), plex_movies(title_sort), lb_entries(list_id), matches(lb_entry_id), matches(plex_movie_id), matches(confidence), plex_movies GIN index on genres.

Status: initial SQLAlchemy models and Alembic migration exist. Still needs live migration test
against Docker Postgres.

---

## Phase 4 — Plex ingestion job 🟡 (first pass implemented)

`src/plexsort/ingest/plex.py`

- Use Plex API: `GET {PLEX_URL}/library/sections/{section_key}/all?X-Plex-Token={token}`
- Pull all movies in one or more pages (handle pagination via `X-Plex-Container-Start`)
- For each movie, also fetch `GET {PLEX_URL}/library/metadata/{ratingKey}?X-Plex-Token={token}` to get full metadata including `Media` items for resolution/codec — BUT extract only safe fields, never file paths
- Write pattern: truncate `plex_movies` table, re-insert all rows (full rebuild, not incremental). Set `last_synced_at = now()` on all rows.
- Expose as admin API endpoint: `POST /api/admin/sync/plex` (triggers sync, returns job ID or streams progress)

PLEX_LIBRARY env var is the section title; look up section key by `GET {PLEX_URL}/library/sections/` first.

Status: real sync has completed. Pagination support exists and fixture tests cover
path stripping. Still needs broader failure-mode tests and scheduled sync decisions.

---

## Phase 5 — Letterboxd ingestion 🟡 (first pass implemented)

### URL scraper (`src/plexsort/ingest/lb_scrape.py`)
- Target: `https://letterboxd.com/<user>/list/<list-slug>/` or `https://letterboxd.com/<user>/watchlist/`
- Pages: follow pagination (`?page=N`) until no more entries
- Rate limit: 1 req/sec, exponential backoff on 429/503, max 3 retries
- Parse each `li.poster-container` → `data-film-slug`, film title `h2.headline-2 a`, year from film detail or `em.year`
- On failure: store partial results with a `scrape_error` note on the lb_list row; surface to admin

### CSV parser (`src/plexsort/ingest/lb_csv.py`)
- Letterboxd exports a zip containing CSVs: `watchlist.csv`, `watched.csv`, `diary.csv`, `ratings.csv`, `lists/<list-name>.csv`
- Each has columns: `Date`,`Name`,`Year`,`Letterboxd URI`
- Parse uploaded file (zip or single csv), detect type, map to lb_entries schema
- Admin endpoint: `POST /api/admin/lists/upload` (multipart form)

Status: first-pass CSV/zip import and URL scraper exist. Needs fixture tests and live scrape
validation.

---

## Phase 6 — Matching engine 🟡 (first pass implemented)

`src/plexsort/match/engine.py`

### Normalization
```python
import re, unicodedata

def normalize(title: str) -> str:
    title = title.lower()
    title = unicodedata.normalize("NFKD", title)
    title = re.sub(r"[^\w\s]", "", title)       # strip punctuation
    title = re.sub(r"^(the|a|an)\s+", "", title) # strip leading articles
    title = re.sub(r"\s+", " ", title).strip()
    return title
```

### Matching priority
1. **TMDB ID** (high confidence) — if lb_entry has a resolved TMDB id AND plex_movie has one, match directly. (placeholder for later)
2. **Exact normalized title + exact year** → confidence = 'high'
3. **Exact normalized title + year within ±1** → confidence = 'medium'
4. **Fuzzy normalized title (Levenshtein ratio ≥ 0.9) + year within ±1** → confidence = 'low'
5. **No match** → plex_movie_id = NULL, confidence = 'none'

Run matching as a post-ingestion step: after any Plex sync or LB ingestion, re-run match for affected entries.

Expose: `POST /api/admin/match/run` to re-run full matching pass.

Status: title/year matching exists with initial unit tests. TMDB matching remains deferred.

---

## Phase 7 — Public API 🟡 (first pass implemented)

`src/plexsort/api/public.py`

All responses use Pydantic schemas that explicitly list safe fields (no file paths, no internal IDs beyond what's needed).

### Endpoints

`GET /api/movies` — paginated, filterable, sortable Plex library
- Query params: `page`, `per_page`, `sort` (column), `dir` (asc/desc), `genre`, `year`, `year_min`, `year_max`, `resolution`, `content_rating`, `watched` (bool), `q` (title search)
- Response: `{ total, page, items: [MoviePublic] }`

`GET /api/movies/{plex_rating_key}` — single movie detail

`GET /api/lists` — all saved Letterboxd lists

`GET /api/lists/{id}/compare` — gap/overlap report for one list vs Plex library
- Returns: `{ in_both: [...], plex_only: [...], lb_only: [...], coverage_pct: float }`
- The public UI treats `lb_only` as `Missing From Plex`, which is the acquisition/coverage
  todo list.

`GET /api/stats` — summary counts (total movies, total watched, lists loaded, etc.)
`GET /api/health/metrics` — public health readout for library/match/list coverage
`GET /api/posters/{plex_rating_key}` — public poster proxy backed by Plex API

### Public schema (safe fields only)
```python
class MoviePublic(BaseModel):
    plex_rating_key: str
    title: str
    title_sort: str
    year: int | None
    tmdb_id: str | None
    imdb_id: str | None
    genres: list[str]
    directors: list[str]
    duration_ms: int | None
    resolution: str | None
    video_codec: str | None
    audience_rating: float | None
    rating: float | None
    content_rating: str | None
    studio: str | None
    summary: str | None
    thumb_url: str | None
    added_at: datetime | None
    last_viewed_at: datetime | None
    view_count: int
```

Status: first-pass endpoints exist. Needs API integration tests against a test database.
Current checkpoint: isolated SQLite route tests now cover health, stats, movies, lists,
compare, admin movie search, admin manual review patching, and admin job status reads.

---

## Phase 8 — Admin API 🟡 (progress-enabled first pass implemented)

`src/plexsort/api/admin.py`

NOTE: Admin routes are intentionally public. Caddy no longer applies Basic Auth to
`/admin*` or `/api/admin*` by user decision on 2026-06-27.

### Endpoints

`POST /api/admin/sync/plex` — trigger full Plex re-sync (returns 202 + job_id)
`GET  /api/admin/sync/status` — last sync time, row count, any errors
`POST /api/admin/lists/scrape` — `{ "url": "https://letterboxd.com/..." }` → start scrape job
`POST /api/admin/lists/upload` — multipart: upload Letterboxd export zip/csv
`DELETE /api/admin/lists/{id}` — remove a saved list
`POST /api/admin/match/run` — re-run full match pass
`GET  /api/admin/movies/search` - search Plex candidates for manual review
`GET  /api/admin/matches/review` — list low-confidence + unmatched entries
`PATCH /api/admin/matches/{id}` — manually set match / override / mark reviewed

Status: endpoints exist. Long-running sync/import/match actions now queue background jobs and
report progress through `/api/admin/jobs`. Manual review endpoints now support the
first real unmatched queue workflow plus queue summary/filtering.

---

## Phase 9 — Frontend 🟡 (first pass implemented)

`C:\website\plexsort\` — vanilla HTML/CSS/JS, no build step needed.

`index.html` — public browse
- Filterable table of Plex movies (calls `/api/movies`)
- Sidebar filters: genre, year range, resolution, content rating, watched status
- Column headers sortable
- Click any column value → add as filter (Datasette-style)
- List selector: pick a saved Letterboxd list to show coverage overlay

`admin.html` — admin panel (served at `/admin`, publicly reachable)
- Trigger Plex sync button + last-sync timestamp
- Paste Letterboxd URL or upload CSV
- Match review queue with Plex movie search, confirm, and skip/manual-unmatched actions
- Job progress display for sync, import, and matching jobs
- Review queue counts and All/Low/None filter buttons

Public mobile status: filters collapse on small screens, stats stay compact, and movie rows
render as cards instead of a horizontally clipped table.

Design: match the dark aesthetic of cine.favet.net (`--bg: #0d0c18`, gold accents).

Status: first-pass static frontend exists under `frontend/` and has been copied to
`C:\website\plexsort`. Public and admin pages have been deployed behind Caddy.
Current real data snapshot: 1,781 Plex movies, 2 Letterboxd lists, 357 review items.

---

## Phase 10 — Wire up infra ✅ (live)

1. `caddy reload` after updating Caddyfile with the plex.favet.net block (see CLAUDE.md)
2. `cloudflared tunnel route dns favet-tunnel plex.favet.net` (one-time)
3. `Restart-Service cloudflared` in elevated terminal (user runs)
4. `docker compose up -d` from `C:\Users\Justin\Documents\PLEXSORT\`
5. `docker compose run --rm app alembic upgrade head`

Status: Caddy and Cloudflare Tunnel are wired. Public site is live at `https://plex.favet.net`.
Public API and admin routes are open; no Basic Auth is required.

---

## Phase 11 — OMDb Data Model and API 🟡 (planned)

Goal: expose the full OMDb enrichment safely without spending more OMDb quota.

Current state:

- `omdb_payload` stores the complete OMDb response for all 1,766 movies with IMDb IDs.
- Existing normalized columns cover only a subset: box office, awards, Metascore,
  IMDb votes, Rotten Tomatoes rating, actors.
- All additional fields should be derived from `omdb_payload`, not by calling OMDb again.

### Backend tasks

- Add first-class API fields for high-value OMDb data:
  - `omdb_imdb_rating`
  - `omdb_rated`
  - `omdb_released`
  - `omdb_runtime`
  - `omdb_genre`
  - `omdb_writer`
  - `omdb_plot`
  - `omdb_language`
  - `omdb_country`
  - `omdb_poster`
  - `omdb_ratings`
- Prefer computed response fields from `omdb_payload` unless a field needs indexing or sorting.
- Add dedicated DB columns only for fields that need fast filtering/sorting.
- Add tests proving public responses still exclude secrets, paths, and raw internal-only fields.

### Exit criteria

- `/api/movies` and `/api/movies/{plex_rating_key}` expose selected OMDb fields.
- No OMDb API calls are required for backfill.
- Route tests cover the new fields and safe response shape.
- `ruff`, `compileall`, `pytest`, `mypy`, and JS syntax checks pass.

---

## Phase 12 — Movie Detail Experience 🟡 (planned)

Goal: make the new data useful without making the browse table unreadable.

### UI tasks

- Add a movie detail drawer or modal opened from a movie row/card.
- Group fields into compact sections:
  - Overview: plot, runtime, released, rated, country, language
  - Ratings: Plex ratings, IMDb rating/votes, Metascore, Rotten Tomatoes
  - Cast/Crew: directors, writer, actors
  - Technical: resolution, bitrate, codec, duration, watched status
  - Lists: selected Letterboxd list coverage/match status
- Keep long text out of table cells: plot, awards, actors, writer.
- Render missing values quietly; do not show noisy `N/A`.

### Exit criteria

- Desktop and mobile can inspect all important movie data from one interaction.
- No horizontal overflow on mobile.
- Detail view works for movies with partial OMDb data and for the 15 movies without IMDb IDs.

---

## Phase 13 — Desktop Column System 🟡 (planned)

Goal: make many columns usable on desktop through presets and user choice.

### Column presets

- `Library`: poster, title, year, runtime, resolution, watched, added
- `Ratings`: title, year, Plex rating, audience rating, IMDb, Metascore, Rotten Tomatoes
- `Release`: title, year, released, rated, country, language, studio
- `Technical`: title, resolution, bitrate, codec, duration, added
- `People`: title, director, writer, actors
- `OMDb`: title plus key OMDb fields

### UI tasks

- Add a column picker with preset buttons and checkboxes.
- Persist column choices in `localStorage`.
- Keep default table compact.
- Add sticky title/poster behavior only if it stays smooth and readable.
- Make CSV export support current visible columns and full enriched data.

### Exit criteria

- Desktop table can show wide data sets without overwhelming the default view.
- Column choices survive reload.
- Export reflects the chosen view.

---

## Phase 14 — Mobile Browse Redesign 🟡 (planned)

Goal: keep mobile fast and readable with enriched data.

### Mobile tasks

- Keep mobile movie cards compact:
  - poster
  - title/year
  - one or two rating chips
  - resolution/watched indicator
- Move detailed OMDb data into the detail drawer/page.
- Replace dense sidebar controls with collapsible filter groups and active filter chips.
- Avoid horizontal tables on mobile entirely.
- Verify at common widths: 390px, 430px, 768px.

### Exit criteria

- Mobile has no page-level horizontal overflow.
- Cards remain scannable with real data.
- All enriched fields are reachable from the detail view.

---

## Phase 15 — Advanced Filters and Sorting 🟡 (planned)

Goal: let the enriched data answer real collection questions.

### Filter/sort additions

- Sort by IMDb rating, Metascore, Rotten Tomatoes, box office, release date, runtime, bitrate.
- Filter by rated/content rating, country, language, decade/year range, minimum ratings,
  has box office, has poster, and missing OMDb field.
- Keep every sortable/filterable field whitelisted in backend code.

### Exit criteria

- Backend tests cover new sort/filter whitelists.
- Frontend filters are ergonomic on desktop and mobile.
- No arbitrary SQL or raw user-controlled sort fields.

---

## Phase 16 — Polish, Verification, and Deployment 🟡 (planned)

Goal: ship the enriched PlexSort experience cleanly.

### Verification tasks

- Run full local checkpoint:
  - `python -m ruff check .`
  - `python -m compileall src alembic tests`
  - `python -m pytest`
  - `python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort`
  - `node --check frontend\assets\app.js`
  - `node --check frontend\assets\admin.js`
- Browser smoke test desktop public browse, mobile public browse, movie detail drawer,
  column presets, and exports.
- Deploy backend container and copy static frontend to `C:\website\plexsort`.
- Update `STATUS.md` with validation and live counts.

### Exit criteria

- Site is live with enriched details.
- No secret/path leakage in API responses or static frontend.
- Mobile and desktop layouts are verified with real data.

---

## Open questions (for user to decide when reached)

- What is your Plex server's local IP/port? (goes in `.env` as `PLEX_URL`)
- What is the library section name in Plex? Default assumption: `Movies`
- What port does Plex listen on? Default assumption: 32400
- Do you want the Plex sync to run on a schedule automatically, and if so what interval? (hourly? daily? manual-only for now?)
- Should Letterboxd list scrapes auto-refresh on a schedule, or manual-only?
- TMDB API key — when you have one, add `TMDB_API_KEY` to `.env` and the matching engine will use it

---

## Ports summary

| Service | Port |
|---|---|
| PlexSort API | 8004 (host-exposed) |
| PlexSort Postgres | internal Docker network only |
| SHOWCATCHER Postgres | 5432 |
| Cinemagic | 3737 |
| Wordle | 8000 |
