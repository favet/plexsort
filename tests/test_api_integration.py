from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from plexsort.db import get_db
from plexsort.main import app
from plexsort.models import Base, JobRun, LetterboxdEntry, LetterboxdList, Match, PlexMovie


@pytest.fixture()
def api_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = testing_session()
    seed_database(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(api_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield api_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def seed_database(db: Session) -> None:
    movie_one = PlexMovie(
        plex_rating_key="m1",
        title="The Matrix",
        title_sort="Matrix",
        year=1999,
        tmdb_id="603",
        imdb_id="tt0133093",
        genres=["Science Fiction", "Action"],
        directors=["Lana Wachowski", "Lilly Wachowski"],
        duration_ms=8172000,
        resolution="1080",
        video_codec="h264",
        audience_rating=None,
        rating=None,
        content_rating="R",
        studio="Warner Bros.",
        summary="A computer hacker learns about the true nature of reality.",
        thumb_url="/library/metadata/m1/thumb",
        added_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_viewed_at=datetime(2026, 1, 2, tzinfo=UTC),
        view_count=1,
        last_synced_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    movie_two = PlexMovie(
        plex_rating_key="m2",
        title="Arrival",
        title_sort="Arrival",
        year=2016,
        tmdb_id="329865",
        imdb_id="tt2543164",
        genres=["Science Fiction", "Drama"],
        directors=["Denis Villeneuve"],
        duration_ms=6960000,
        resolution="4K",
        video_codec="hevc",
        audience_rating=None,
        rating=None,
        content_rating="PG-13",
        studio="Paramount",
        summary="A linguist works with the military to communicate with visitors.",
        thumb_url="/library/metadata/m2/thumb",
        added_at=datetime(2026, 1, 4, tzinfo=UTC),
        last_viewed_at=None,
        view_count=0,
        last_synced_at=datetime(2026, 1, 5, tzinfo=UTC),
    )
    db.add_all([movie_one, movie_two])
    db.flush()

    lb_list = LetterboxdList(
        name="Sample List",
        source_type="csv_export",
        source_url=None,
        list_kind="list",
        entry_count=2,
    )
    db.add(lb_list)
    db.flush()

    matched_entry = LetterboxdEntry(
        list_id=lb_list.id,
        title="The Matrix",
        year=1999,
        lb_film_slug="the-matrix",
        lb_film_url="https://letterboxd.com/film/the-matrix/",
        list_position=1,
    )
    unmatched_entry = LetterboxdEntry(
        list_id=lb_list.id,
        title="No Such Film",
        year=2020,
        lb_film_slug="no-such-film",
        lb_film_url="https://letterboxd.com/film/no-such-film/",
        list_position=2,
    )
    db.add_all([matched_entry, unmatched_entry])
    db.flush()

    db.add_all(
        [
            Match(
                lb_entry_id=matched_entry.id,
                plex_movie_id=movie_one.id,
                confidence="low",
                match_method="exact_title_near_year",
                reviewed=False,
            ),
            Match(
                lb_entry_id=unmatched_entry.id,
                plex_movie_id=None,
                confidence="none",
                match_method="none",
                reviewed=False,
            ),
            JobRun(
                id="job-1",
                job_type="match_run",
                status="completed",
                phase="complete",
                message="Done",
                current=2,
                total=2,
                result={"matched_count": 2},
                created_at=datetime(2026, 1, 6, tzinfo=UTC),
                updated_at=datetime(2026, 1, 6, tzinfo=UTC),
                finished_at=datetime(2026, 1, 6, tzinfo=UTC),
            ),
        ]
    )
    db.commit()


def response_json(response: Any) -> Any:
    assert response.status_code == 200
    return response.json()


def test_public_api_uses_safe_response_shapes(client: TestClient) -> None:
    assert response_json(client.get("/health")) == {"status": "ok"}
    assert response_json(client.get("/api/stats")) == {
        "total_movies": 2,
        "total_watched": 1,
        "lists_loaded": 1,
    }

    movie_page = response_json(client.get("/api/movies?per_page=1&sort=title"))
    assert movie_page["total"] == 2
    assert len(movie_page["items"]) == 1
    forbidden_fields = {"id", "file", "file_path", "media_path", "plex_token", "plex_url"}
    assert forbidden_fields.isdisjoint(movie_page["items"][0])

    lists = response_json(client.get("/api/lists"))
    assert lists[0]["name"] == "Sample List"

    comparison = response_json(client.get(f"/api/lists/{lists[0]['id']}/compare"))
    assert comparison["coverage_pct"] == 50.0
    assert [item["title"] for item in comparison["in_both"]] == ["The Matrix"]
    assert [item["title"] for item in comparison["lb_only"]] == ["No Such Film"]
    assert [item["title"] for item in comparison["plex_only"]] == ["Arrival"]


def test_admin_review_search_and_patch_workflow(client: TestClient) -> None:
    candidates = response_json(client.get("/api/admin/movies/search?q=Matrix&limit=5"))
    assert candidates[0]["title"] == "The Matrix"
    assert isinstance(candidates[0]["id"], int)
    assert "file_path" not in candidates[0]

    summary = response_json(client.get("/api/admin/matches/review/summary"))
    assert summary == {
        "pending_total": 2,
        "pending_low": 1,
        "pending_none": 1,
        "reviewed_total": 0,
    }

    low_items = response_json(client.get("/api/admin/matches/review?confidence=low&limit=10"))
    assert [item["confidence"] for item in low_items] == ["low"]

    review_items = response_json(client.get("/api/admin/matches/review?confidence=none&limit=1"))
    assert len(review_items) == 1
    assert review_items[0]["confidence"] == "none"
    match_id = review_items[0]["match_id"]
    movie_id = candidates[0]["id"]

    patched = response_json(
        client.patch(
            f"/api/admin/matches/{match_id}",
            json={
                "plex_movie_id": movie_id,
                "confidence": "high",
                "match_method": "manual",
                "reviewed": True,
            },
        )
    )
    assert patched["reviewed"] is True
    assert patched["confidence"] == "high"
    assert patched["plex_movie"]["title"] == "The Matrix"

    remaining_review_items = response_json(client.get("/api/admin/matches/review?limit=10"))
    assert all(item["match_id"] != match_id for item in remaining_review_items)


def test_admin_job_status_routes(client: TestClient) -> None:
    jobs = response_json(client.get("/api/admin/jobs"))
    assert jobs[0]["id"] == "job-1"
    assert jobs[0]["result"] == {"matched_count": 2}

    job = response_json(client.get("/api/admin/jobs/job-1"))
    assert job["status"] == "completed"

    missing = client.get("/api/admin/jobs/missing")
    assert missing.status_code == 404
