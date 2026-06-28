# PlexSort Testing Checkpoints

Testing is a gate, not a decoration. Each phase should finish with a small, explicit
checkpoint before moving on.

## Always Run Before Calling Work Complete

Install dev dependencies first in a fresh host Python environment:

```powershell
python -m pip install -e .[dev]
```

```powershell
python -m ruff check .
python -m compileall src alembic
python -m pytest
node --check frontend\assets\app.js
node --check frontend\assets\admin.js
```

When dependencies are installed:

```powershell
python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort
```

For Docker/backend checkpoints:

```powershell
docker compose config
docker compose build
docker compose up -d
docker compose run --rm app alembic upgrade head
```

For live deployment checkpoints:

```powershell
curl.exe -s http://localhost:8004/health
curl.exe -s -H "Host: plex.favet.net" http://localhost/api/stats
curl.exe -s -o NUL -w "%{http_code}" -H "Host: plex.favet.net" http://localhost/api/admin/jobs
curl.exe -s -H "Host: plex.favet.net" http://localhost/api/health/metrics
curl.exe -s -L https://plex.favet.net/api/stats
curl.exe -s -L -o NUL -w "%{http_code}" https://plex.favet.net/api/admin/jobs
```

Expected result: public and admin endpoints return `200`. Admin auth was removed by
user decision on 2026-06-27.

## Checkpoint Gates

### Backend Scaffold

- App package imports.
- Ruff passes.
- Python syntax compilation passes.
- Docker Compose config validates.
- Unit tests for pure logic pass.

### Database Schema

- Alembic migration applies to a fresh database.
- Alembic downgrade/upgrade is tested before schema gets real data.
- Indexes exist for documented query paths.
- No columns are added for filesystem paths or internal Plex server paths.

### Public API

- Every public endpoint has a response model.
- Public schemas explicitly list fields.
- Tests assert forbidden fields are absent.
- Sort fields use a whitelist.
- Filters are expressed with SQLAlchemy constructs, not raw SQL text from users.

### Admin API

- All admin endpoints live under `/api/admin`.
- Caddy config does not protect `/admin*` or `/api/admin*`; this is intentional.
- Mutation routes are not reachable from the public API namespace.
- Long-running work creates job records and reports progress through `/api/admin/jobs`.
- Manual review routes are publicly reachable.

### Plex Ingestion

- Test with a small fixture XML response.
- Test that media file path fields are ignored even if Plex returns them.
- Test library section lookup by Plex library title.
- Test pagination before using a large library.
- Test failure behavior when token or URL is missing.

### Letterboxd Ingestion

- Test CSV import with watchlist, watched, diary, ratings, and custom list shapes.
- Test zip upload containing multiple CSVs.
- Test URL scrape against a known small public list.
- Test partial scrape failure records an error without corrupting existing data.

### Matching

- Test exact title/year match.
- Test exact title with near-year match.
- Test fuzzy match threshold.
- Test unmatched entry behavior.
- Test manual review override.

### Frontend

- JavaScript syntax checks pass with `node --check`.
- Smoke test public browse at desktop and mobile sizes.
- Verify filters, sorting, and pagination do not shift layout.
- Verify admin page handles loading, empty, success, and error states.
- Verify no secret or Plex token appears in browser source or network-visible static assets.

### Pre-Public Launch

- Run full test suite.
- Start app through Docker.
- Apply migrations.
- Sync Plex once.
- Import or scrape one Letterboxd list.
- Run matching.
- Inspect public API JSON for forbidden fields.
- Verify `/admin` and `/api/admin` are reachable with no auth.
- Verify public endpoints require no auth.
