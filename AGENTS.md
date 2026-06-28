# PlexSort — plex.favet.net

Plex × Letterboxd analytics site. Publicly browsable Plex library with Letterboxd list comparison and gap views.

## File layout

| What | Path |
|---|---|
| Backend source | `C:\Users\Justin\Documents\PLEXSORT\` (this directory) |
| Static frontend | `C:\website\plexsort\` |
| Backend port | `8004` |
| Infra AGENTS.md | `C:\Users\Justin\.cloudflared\AGENTS.md` |

## Documentation trail

Read these before making changes:

- `README.md` — documentation map and quick start
- `PLAN.md` — phase plan and current phase status
- `STATUS.md` — running project log, decisions, validation, known gaps
- `TESTING.md` — required checkpoint testing gates
- `PLEX_SETUP.md` — how to find Plex environment values

## Stack

- **Language**: Python 3.11+
- **API framework**: FastAPI + uvicorn
- **ORM / migrations**: SQLAlchemy 2.x + Alembic
- **DB driver**: psycopg2-binary
- **Scraping**: requests + beautifulsoup4
- **Validation**: pydantic 2.x
- **Tooling**: black (line-length=100), ruff, mypy (strict)
- **Runtime**: Docker compose (backend + postgres containers)

## Infrastructure pattern

Follows the same convention as cinemagic and wordle-solver on this host:

1. Docker compose runs the app container (port 8004) and a postgres container (internal only)
2. Caddy reverse-proxies `plex.favet.net` to the app
3. Cloudflare Tunnel carries traffic from the public subdomain to Caddy

**Caddy block to add** (`C:\Users\Justin\.cloudflared\Caddyfile`):
```
http://plex.favet.net {
    rewrite /admin /admin.html
    reverse_proxy /api/* localhost:8004
    root * C:\website\plexsort
    file_server
}
```

**Tunnel ingress to add** (`C:\Users\Justin\.cloudflared\config.yml`, before the catch-all):
```yaml
  - hostname: plex.favet.net
    service: http://localhost:80
```

**DNS route** (one-time, from any terminal):
```
cloudflared tunnel route dns favet-tunnel plex.favet.net
```

**Reload/restart** (see infra AGENTS.md for details):
- Caddy: `caddy reload --config C:\Users\Justin\.cloudflared\Caddyfile`
- cloudflared: `Restart-Service cloudflared` (requires elevated terminal — user runs manually)

## Auth

- **Public browse/API**: no auth — fully open
- **Admin routes (`/admin*`, `/api/admin*`)**: no auth — fully open by user decision on 2026-06-27
- Keep Plex token and server filesystem paths out of responses even though the site is open.

## Postgres

Own isolated container (not the SHOWCATCHER postgres). Internal Docker network only — not exposed to host.
Connection string: `postgresql://plexsort:plexsort@db:5432/plexsort`

## Environment

All secrets go in `.env` (never committed). See `.env.example` for required vars:
- `PLEX_URL` — Plex server base URL (e.g. `http://192.168.1.x:32400`)
- `PLEX_TOKEN` — Plex API token
- `PLEX_LIBRARY` — Plex library section title inside Plex (e.g. `Movies`), not a filesystem directory
- `DATABASE_URL` — set in docker-compose, not needed in .env for Docker runs

See `PLEX_SETUP.md` for where to find these values.

## Key constraints (never violate)

- File paths and any server-revealing fields (library paths, internal hostnames) MUST be excluded from all public API responses — enforced at the serializer/schema layer, not just frontend
- No arbitrary SQL on public-facing routes
- Plex data via API only — never touch Plex's internal SQLite
- Letterboxd via URL scrape or exported CSV — no Letterboxd API

## Testing checkpoints

Run and record checkpoint results in `STATUS.md` before calling a phase complete.
Minimum local checks:

```
python -m ruff check .
python -m compileall src alembic
python -m pytest
```

When dependencies are installed, also run:

```
python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort
```

## Data sources

**Plex** — pull-and-replace ingestion via Plex API, scheduled. Postgres is the source of truth; fully rebuildable from a fresh pull.

**Letterboxd** — two ingestion paths, same normalized schema:
1. Paste a public list/watchlist URL → scrape page(s) for title/year/position (polite, rate-limited, best-effort)
2. Upload a Letterboxd export CSV/zip (watchlist, watched, diary, ratings, custom lists)

## Matching engine

- Primary: normalized title + year (Levenshtein or simple normalize-and-compare)
- Future: TMDB ID resolution (no API key yet — add later)
- Confidence/match-quality flag per match pair
- Low-confidence and unmatched entries surface in admin review queue

## Running locally

```
cd C:\Users\Justin\Documents\PLEXSORT
cp .env.example .env   # fill in Plex creds
docker compose up -d
docker compose run --rm app alembic upgrade head
```

API available at `http://localhost:8004`.
