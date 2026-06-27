from __future__ import annotations

from fastapi import FastAPI

from plexsort.api import admin, public

app = FastAPI(title="PlexSort", version="0.1.0")
app.include_router(public.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

