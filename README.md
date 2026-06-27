# PlexSort

PlexSort is a Plex and Letterboxd analytics site for browsing a Plex movie library
and comparing it with Letterboxd lists, watchlists, and exports.

## Documentation Map

- `AGENTS.md` - durable agent instructions, stack, constraints, infra notes.
- `PLAN.md` - phase-by-phase implementation plan and current phase status.
- `STATUS.md` - running project log of what happened and what is true now.
- `TESTING.md` - checkpoint testing policy and gates.
- `PLEX_SETUP.md` - how to find `PLEX_URL`, `PLEX_TOKEN`, and `PLEX_LIBRARY`.
- `.env.example` - local environment template.
- `frontend/` - tracked static frontend source, copied to `C:\website\plexsort`.

## Current Status

The site is live at `https://plex.favet.net` with real Plex data, two imported
Letterboxd lists, progress-tracked admin jobs, and first-pass manual match review
tools. Admin pages and admin APIs are protected by Caddy Basic Auth.
See `STATUS.md` before making the next change.

## Local Development

```powershell
copy .env.example .env
# Fill in Plex values from PLEX_SETUP.md
docker compose up -d
docker compose run --rm app alembic upgrade head
```

API target: `http://localhost:8004`

## Checkpoint Tests

```powershell
python -m ruff check .
python -m compileall src alembic
python -m pytest
node --check frontend\assets\app.js
node --check frontend\assets\admin.js
```

When dev dependencies are installed:

```powershell
python -m mypy --no-incremental --cache-dir .mypy_cache src/plexsort
```

Current note: the runtime/test gates are green, but `mypy` is not yet green in the
host Python environment. See `STATUS.md` for the exact blockers.
