from __future__ import annotations

from collections.abc import Generator
from typing import Any
from xml.etree import ElementTree

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from plexsort.config import Settings
from plexsort.ingest import plex as plex_ingest
from plexsort.models import Base, PlexMovie
from plexsort.schemas import MoviePublic


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


def xml(text: str) -> ElementTree.Element:
    return ElementTree.fromstring(text)


def test_sync_plex_movies_paginates_and_strips_file_paths(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        PLEX_URL="http://plex.local:32400",
        PLEX_TOKEN="token",
        PLEX_LIBRARY="Movies",
    )
    requested_library_starts: list[int] = []

    def fake_request_xml(
        settings: Settings,
        path: str,
        params: dict[str, str] | None = None,
    ) -> ElementTree.Element:
        if path == "/library/sections/":
            return xml('<MediaContainer><Directory title="Movies" key="1" /></MediaContainer>')

        if path == "/library/sections/1/all":
            start = int((params or {}).get("X-Plex-Container-Start", "0"))
            requested_library_starts.append(start)
            if start == 0:
                return xml(
                    '<MediaContainer size="1" totalSize="2">'
                    '<Video ratingKey="101" title="Arrival" />'
                    "</MediaContainer>"
                )
            if start == 1:
                return xml(
                    '<MediaContainer size="1" totalSize="2">'
                    '<Video ratingKey="102" title="The Matrix" />'
                    "</MediaContainer>"
                )
            return xml('<MediaContainer size="0" totalSize="2" />')

        if path == "/library/metadata/101":
            return xml(
                '<MediaContainer><Video ratingKey="101" title="Arrival" titleSort="Arrival" '
                'year="2016" duration="6960000" contentRating="PG-13" studio="Paramount" '
                'summary="A linguist works with visitors." thumb="/thumb/101" addedAt="1700000000" '
                'viewCount="1">'
                '<Guid id="tmdb://329865" /><Guid id="imdb://tt2543164" />'
                '<Genre tag="Science Fiction" /><Director tag="Denis Villeneuve" />'
                '<Media videoResolution="4K" videoCodec="hevc">'
                '<Part bitrate="24000" file="D:\\Movies\\Arrival\\Arrival.mkv" />'
                "</Media></Video></MediaContainer>"
            )

        if path == "/library/metadata/102":
            return xml(
                '<MediaContainer><Video ratingKey="102" title="The Matrix" titleSort="Matrix" '
                'year="1999" duration="8172000" contentRating="R" studio="Warner Bros." '
                'summary="A hacker wakes up." thumb="/thumb/102" addedAt="1700000001" '
                'lastViewedAt="1700000500" viewCount="2">'
                '<Guid id="tmdb://603" /><Guid id="imdb://tt0133093" />'
                '<Genre tag="Action" /><Director tag="Lana Wachowski" />'
                '<Media bitrate="8500" videoResolution="1080" videoCodec="h264">'
                '<Part file="D:\\Movies\\The Matrix\\The Matrix.mkv" />'
                "</Media></Video></MediaContainer>"
            )

        raise AssertionError(f"Unexpected Plex path: {path}")

    progress_events: list[tuple[int, int | None, str, str]] = []
    monkeypatch.setattr(plex_ingest, "_request_xml", fake_request_xml)

    movie_count = plex_ingest.sync_plex_movies(
        db_session,
        settings,
        lambda current, total, phase, message: progress_events.append(
            (current, total, phase, message)
        ),
    )

    assert movie_count == 2
    assert requested_library_starts == [0, 1]
    assert progress_events[-1][2] == "plex_complete"

    movies = list(db_session.scalars(select(PlexMovie).order_by(PlexMovie.title_sort)).all())
    assert [movie.title for movie in movies] == ["Arrival", "The Matrix"]
    assert movies[0].tmdb_id == "329865"
    assert movies[0].resolution == "4K"
    assert movies[0].video_codec == "hevc"
    assert movies[0].bitrate_kbps == 24000  # from <Part bitrate>
    assert movies[1].bitrate_kbps == 8500   # from <Media bitrate>

    public_payload = [MoviePublic.model_validate(movie).model_dump() for movie in movies]
    assert all("file" not in movie for movie in public_payload)
    assert "D:\\Movies" not in str(public_payload)

    # Second sync should preserve OMDb enrichment on existing rows.
    movies[0].omdb_metascore = 95
    db_session.commit()

    plex_ingest.sync_plex_movies(db_session, settings)
    refreshed = list(db_session.scalars(select(PlexMovie).order_by(PlexMovie.title_sort)).all())
    assert len(refreshed) == 2
    assert refreshed[0].omdb_metascore == 95  # preserved across sync


def test_movie_from_video_ignores_path_bearing_media_parts() -> None:
    video = xml(
        '<Video ratingKey="201" title="Safe Movie">'
        '<Media videoResolution="1080" videoCodec="h264">'
        '<Part file="D:\\Private\\Safe Movie.mkv" />'
        "</Media></Video>"
    )

    payload: dict[str, Any] = plex_ingest.movie_from_video(
        video,
        synced_at=plex_ingest.datetime.now(plex_ingest.UTC),
    )

    assert payload["plex_rating_key"] == "201"
    assert payload["resolution"] == "1080"
    assert "file" not in payload
    assert "D:\\Private" not in str(payload)
