from __future__ import annotations

import csv
import io
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from plexsort.config import Settings, get_settings
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
        bitrate_kbps=8500,
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
        omdb_payload={
            "Title": "The Matrix",
            "Rated": "R",
            "Released": "31 Mar 1999",
            "Runtime": "136 min",
            "Genre": "Action, Sci-Fi",
            "Writer": "Lilly Wachowski, Lana Wachowski",
            "Actors": "Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss",
            "Plot": "A hacker discovers the nature of his reality.",
            "Language": "English",
            "Country": "United States, Australia",
            "Poster": "https://example.test/matrix.jpg",
            "imdbRating": "8.7",
            "Metascore": "73",
            "Ratings": [
                {"Source": "Internet Movie Database", "Value": "8.7/10"},
                {"Source": "Rotten Tomatoes", "Value": "83%"},
            ],
        },
        omdb_box_office="$467,231,855",
        omdb_box_office_raw=467231855,
        omdb_metascore=73,
        omdb_rt_rating="83%",
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
        bitrate_kbps=24000,
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


def response_csv(response: Any) -> list[list[str]]:
    assert response.status_code == 200
    return list(csv.reader(io.StringIO(response.text)))


def test_public_api_uses_safe_response_shapes(client: TestClient) -> None:
    assert response_json(client.get("/health")) == {"status": "ok"}
    assert response_json(client.get("/api/stats")) == {
        "total_movies": 2,
        "total_watched": 1,
        "lists_loaded": 1,
    }

    movie_page = response_json(client.get("/api/movies?per_page=1&sort=title&q=Matrix"))
    assert movie_page["total"] == 1
    assert len(movie_page["items"]) == 1
    movie = movie_page["items"][0]
    forbidden_fields = {
        "id",
        "file",
        "file_path",
        "media_path",
        "plex_token",
        "plex_url",
        "omdb_payload",
    }
    assert forbidden_fields.isdisjoint(movie_page["items"][0])
    assert movie["omdb_imdb_rating"] == "8.7"
    assert movie["omdb_rated"] == "R"
    assert movie["omdb_released"] == "31 Mar 1999"
    assert movie["omdb_runtime"] == "136 min"
    assert movie["omdb_writer"] == "Lilly Wachowski, Lana Wachowski"
    assert movie["omdb_plot"] == "A hacker discovers the nature of his reality."
    assert movie["omdb_language"] == "English"
    assert movie["omdb_country"] == "United States, Australia"
    assert movie["omdb_ratings"] == [
        {"Source": "Internet Movie Database", "Value": "8.7/10"},
        {"Source": "Rotten Tomatoes", "Value": "83%"},
    ]

    lists = response_json(client.get("/api/lists"))
    assert lists[0]["name"] == "Sample List"

    comparison = response_json(client.get(f"/api/lists/{lists[0]['id']}/compare"))
    assert comparison["coverage_pct"] == 50.0
    assert [item["title"] for item in comparison["in_both"]] == ["The Matrix"]
    assert [item["title"] for item in comparison["lb_only"]] == ["No Such Film"]
    assert [item["title"] for item in comparison["plex_only"]] == ["Arrival"]

    enriched_filter = response_json(
        client.get("/api/movies?country=Australia&language=English&min_imdb_rating=8.5")
    )
    assert enriched_filter["total"] == 1
    assert enriched_filter["items"][0]["title"] == "The Matrix"

    assert response_json(client.get("/api/movies?sort=imdb_rating&dir=desc"))["total"] == 2
    box_office_sorted = response_json(client.get("/api/movies?sort=box_office&dir=desc"))
    assert box_office_sorted["items"][0]["title"] == "The Matrix"

    has_omdb_yes = response_json(client.get("/api/movies?has_omdb=true"))
    assert has_omdb_yes["total"] == 1
    assert has_omdb_yes["items"][0]["title"] == "The Matrix"

    has_omdb_no = response_json(client.get("/api/movies?has_omdb=false"))
    assert has_omdb_no["total"] == 1
    assert has_omdb_no["items"][0]["title"] == "Arrival"


def test_movies_csv_export_supports_visible_and_full_enriched_columns(
    client: TestClient,
) -> None:
    selected = response_csv(
        client.get(
            "/api/export/movies-csv"
            "?q=Matrix&columns=title&columns=imdb_rating&columns=country"
        )
    )
    assert selected == [
        ["Title", "IMDb Rating", "Country"],
        ["The Matrix", "8.7", "United States, Australia"],
    ]

    full = response_csv(client.get("/api/export/movies-csv?q=Matrix&columns=all"))
    headers = full[0]
    assert "Plot" in headers
    assert "OMDb Poster" in headers
    assert "omdb_payload" not in headers
    assert full[1][headers.index("Plot")] == "A hacker discovers the nature of his reality."


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


def test_public_health_metrics_report_match_and_coverage(client: TestClient) -> None:
    metrics = response_json(client.get("/api/health/metrics"))

    assert metrics["total_movies"] == 2
    assert metrics["letterboxd_entries"] == 2
    assert metrics["matched_entries"] == 1
    assert metrics["unmatched_entries"] == 1
    assert metrics["match_rate"] == 50.0
    assert metrics["low_confidence"] == 1
    assert metrics["no_match"] == 1
    assert metrics["pending_review"] == 2
    assert metrics["list_coverage"] == [
        {
            "id": 1,
            "name": "Sample List",
            "entry_count": 2,
            "in_plex": 1,
            "missing": 1,
            "coverage_pct": 50.0,
        }
    ]


def test_public_poster_proxy_uses_plex_token_without_exposing_it(
    api_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pytest.TempPathFactory,
) -> None:
    import io as _io

    from PIL import Image

    buf = _io.BytesIO()
    Image.new("RGB", (10, 15), color=(100, 100, 100)).save(buf, format="JPEG")
    tiny_jpeg = buf.getvalue()

    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        content = tiny_jpeg
        headers = {"content-type": "image/jpeg"}

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, params: dict[str, str], timeout: int) -> FakeResponse:
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return FakeResponse()

    def override_get_db() -> Generator[Session, None, None]:
        yield api_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        PLEX_URL="http://plex.local:32400",
        PLEX_TOKEN="secret-token",
        PLEX_LIBRARY="Movies",
    )
    monkeypatch.setattr("plexsort.api.public.requests.get", fake_get)
    monkeypatch.setattr("plexsort.api.public.POSTER_CACHE_DIR", tmp_path)
    try:
        with TestClient(app) as poster_client:
            response = poster_client.get("/api/posters/m1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert captured["url"] == "http://plex.local:32400/library/metadata/m1/thumb"
    assert captured["params"] == {"X-Plex-Token": "secret-token"}
    assert "secret-token" not in response.text
