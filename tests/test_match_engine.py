from __future__ import annotations

from plexsort.match.engine import choose_match, normalize
from plexsort.models import LetterboxdEntry, PlexMovie


def test_normalize_removes_articles_accents_and_punctuation() -> None:
    assert normalize("The Amelie!") == "amelie"
    assert normalize("À bout de souffle") == "a bout de souffle"


def test_choose_match_prefers_exact_title_and_year() -> None:
    entry = LetterboxdEntry(id=10, list_id=1, title="The Matrix", year=1999)
    movies = [
        PlexMovie(id=1, plex_rating_key="1", title="Matrix", year=1999),
        PlexMovie(id=2, plex_rating_key="2", title="The Matrix Reloaded", year=2003),
    ]

    match = choose_match(entry, movies)

    assert match.plex_movie_id == 1
    assert match.confidence == "high"
    assert match.match_method == "exact_title_year"


def test_choose_match_allows_near_year_for_exact_title() -> None:
    entry = LetterboxdEntry(id=10, list_id=1, title="Nosferatu", year=1922)
    movies = [PlexMovie(id=1, plex_rating_key="1", title="Nosferatu", year=1923)]

    match = choose_match(entry, movies)

    assert match.plex_movie_id == 1
    assert match.confidence == "medium"


def test_choose_match_returns_none_when_no_candidate_matches() -> None:
    entry = LetterboxdEntry(id=10, list_id=1, title="Moonlight", year=2016)
    movies = [PlexMovie(id=1, plex_rating_key="1", title="Sunshine", year=2007)]

    match = choose_match(entry, movies)

    assert match.plex_movie_id is None
    assert match.confidence == "none"

