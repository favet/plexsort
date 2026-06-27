# PlexSort Implementation Plan

Read CLAUDE.md first for all stack/infra decisions. This file is the phase-by-phase build order for the next coding session(s).

---

## Current project status

See `STATUS.md` for the running work log and `TESTING.md` for required checkpoint gates.

As of 2026-06-27:

- Backend foundation is scaffolded.
- Initial schema, API modules, ingestion modules, and matching module exist.
- Initial unit tests exist.
- Frontend is not started.
- Infra wiring is not applied.
- Real Plex sync is blocked on `PLEX_URL`, `PLEX_TOKEN`, and `PLEX_LIBRARY`.

---

## Phase 1 — Scaffold ✅ (complete)

- [x] Decisions locked: Python/FastAPI, Docker compose, own Postgres, HTTP Basic Auth in Caddy for /admin, public browse, no TMDB key yet
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
admin.html          # admin UI (behind Caddy basicauth)
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

Status: first-pass Plex API ingestion exists. Needs real Plex credentials, pagination hardening,
fixture tests, and live sync validation.

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

`GET /api/stats` — summary counts (total movies, total watched, lists loaded, etc.)

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

---

## Phase 8 — Admin API 🟡 (first pass implemented)

`src/plexsort/api/admin.py`

NOTE: Admin route protection is done at the Caddy level (basicauth on /admin*). The FastAPI app itself does NOT need to re-check auth — Caddy strips unauthorized requests before they reach the app. If you later want defense-in-depth, add a middleware that checks for the `Authorization` header, but it's not required.

### Endpoints

`POST /api/admin/sync/plex` — trigger full Plex re-sync (returns 202 + job_id)
`GET  /api/admin/sync/status` — last sync time, row count, any errors
`POST /api/admin/lists/scrape` — `{ "url": "https://letterboxd.com/..." }` → start scrape job
`POST /api/admin/lists/upload` — multipart: upload Letterboxd export zip/csv
`DELETE /api/admin/lists/{id}` — remove a saved list
`POST /api/admin/match/run` — re-run full match pass
`GET  /api/admin/matches/review` — list low-confidence + unmatched entries
`PATCH /api/admin/matches/{id}` — manually set match / override / mark reviewed

Status: endpoints exist. Long-running work currently runs inline and should become background
jobs before the app is treated as production-polished.

---

## Phase 9 — Frontend ⬜ (not started)

`C:\website\plexsort\` — vanilla HTML/CSS/JS, no build step needed.

`index.html` — public browse
- Filterable table of Plex movies (calls `/api/movies`)
- Sidebar filters: genre, year range, resolution, content rating, watched status
- Column headers sortable
- Click any column value → add as filter (Datasette-style)
- List selector: pick a saved Letterboxd list to show coverage overlay

`admin.html` — admin panel (served at `/admin`, with `/api/admin*` also gated by Caddy basicauth)
- Trigger Plex sync button + last-sync timestamp
- Paste Letterboxd URL or upload CSV
- Match review queue (low-confidence entries with "confirm" / "reject" / "manual assign")

Design: match the dark aesthetic of cine.favet.net (`--bg: #0d0c18`, gold accents).

---

## Phase 10 — Wire up infra ⬜ (not started)

1. `caddy reload` after updating Caddyfile with the plex.favet.net block (see CLAUDE.md)
2. `cloudflared tunnel route dns favet-tunnel plex.favet.net` (one-time)
3. `Restart-Service cloudflared` in elevated terminal (user runs)
4. `docker compose up -d` from `C:\Users\Justin\Documents\PLEXSORT\`
5. `docker compose run --rm app alembic upgrade head`

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
