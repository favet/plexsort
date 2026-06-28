from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from plexsort.ingest import omdb
from plexsort.models import Base, PlexMovie


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = testing_session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def add_movie(db: Session, title: str, imdb_id: str) -> None:
    db.add(
        PlexMovie(
            plex_rating_key=imdb_id,
            title=title,
            title_sort=title,
            imdb_id=imdb_id,
            genres=[],
            directors=[],
        )
    )


def test_omdb_enrichment_stops_without_marking_movies_on_rate_limit(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_movie(db_session, "A", "tt1")
    add_movie(db_session, "B", "tt2")
    db_session.commit()

    monkeypatch.setattr(
        omdb,
        "_fetch",
        lambda imdb_id, api_key: omdb.OmdbFetchResult(
            error="Request limit reached!", rate_limited=True
        ),
    )

    result = omdb.run_omdb_enrichment(
        db_session,
        "key",
        lambda current, total, phase, message: None,
        batch_size=2,
        delay=0,
    )

    assert result == {
        "enriched": 0,
        "failed": 0,
        "skipped": 0,
        "remaining": 2,
        "rate_limited": True,
    }
    assert all(movie.omdb_error is None for movie in db_session.query(PlexMovie).all())


def test_omdb_fetch_reads_rate_limit_json_from_http_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def json(self) -> dict[str, str]:
            return {"Response": "False", "Error": "Request limit reached!"}

    monkeypatch.setattr(
        omdb.requests,
        "get",
        lambda url, params, timeout: FakeResponse(),
    )

    result = omdb._fetch("tt1", "key")

    assert result.data is None
    assert result.error == "Request limit reached!"
    assert result.rate_limited is True


def test_omdb_enrichment_stops_without_marking_movies_on_key_error(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_movie(db_session, "A", "tt1")
    db_session.commit()

    monkeypatch.setattr(
        omdb,
        "_fetch",
        lambda imdb_id, api_key: omdb.OmdbFetchResult(error="Invalid API key!", fatal=True),
    )

    result = omdb.run_omdb_enrichment(
        db_session,
        "key",
        lambda current, total, phase, message: None,
        batch_size=1,
        delay=0,
    )
    movie = db_session.query(PlexMovie).one()

    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["remaining"] == 1
    assert result["rate_limited"] is True
    assert movie.omdb_error is None


def test_omdb_enrichment_skips_permanent_failures(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_movie(db_session, "A", "tt1")
    db_session.commit()

    monkeypatch.setattr(
        omdb,
        "_fetch",
        lambda imdb_id, api_key: omdb.OmdbFetchResult(error="Movie not found!"),
    )

    result = omdb.run_omdb_enrichment(
        db_session,
        "key",
        lambda current, total, phase, message: None,
        batch_size=1,
        delay=0,
    )
    movie = db_session.query(PlexMovie).one()

    assert result["failed"] == 1
    assert result["skipped"] == 1
    assert result["remaining"] == 0
    assert result["rate_limited"] is False
    assert movie.omdb_error == "Movie not found!"
    assert movie.omdb_checked_at is not None
