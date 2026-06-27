from __future__ import annotations

from plexsort.schemas import MoviePublic


def test_movie_public_schema_does_not_allow_server_revealing_fields() -> None:
    forbidden_fields = {
        "file",
        "file_path",
        "media_path",
        "library_section_path",
        "plex_token",
        "plex_url",
    }

    assert forbidden_fields.isdisjoint(MoviePublic.model_fields)

