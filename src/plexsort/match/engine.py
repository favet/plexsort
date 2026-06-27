from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from plexsort.models import LetterboxdEntry, Match, PlexMovie


def normalize(title: str) -> str:
    title = title.lower()
    title = unicodedata.normalize("NFKD", title)
    title = re.sub(r"^(the|a|an)\s+", "", title)
    title = "".join(ch for ch in title if not unicodedata.combining(ch))
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


@dataclass(frozen=True)
class MatchCandidate:
    plex_movie_id: int | None
    confidence: str
    match_method: str


def years_close(left: int | None, right: int | None, tolerance: int = 1) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance


def choose_match(entry: LetterboxdEntry, movies: list[PlexMovie]) -> MatchCandidate:
    entry_title = normalize(entry.title)

    for movie in movies:
        if normalize(movie.title) == entry_title and movie.year == entry.year:
            return MatchCandidate(movie.id, "high", "exact_title_year")

    for movie in movies:
        if normalize(movie.title) == entry_title and years_close(movie.year, entry.year):
            return MatchCandidate(movie.id, "medium", "exact_title_near_year")

    best_movie: PlexMovie | None = None
    best_ratio = 0.0
    for movie in movies:
        if not years_close(movie.year, entry.year):
            continue
        ratio = difflib.SequenceMatcher(None, normalize(movie.title), entry_title).ratio()
        if ratio > best_ratio:
            best_movie = movie
            best_ratio = ratio

    if best_movie is not None and best_ratio >= 0.9:
        return MatchCandidate(best_movie.id, "low", "fuzzy_title_year")

    return MatchCandidate(None, "none", "none")


def run_full_match(db: Session) -> int:
    movies = list(db.scalars(select(PlexMovie)).all())
    entries = list(db.scalars(select(LetterboxdEntry)).all())

    db.execute(delete(Match))
    now = datetime.now(UTC)
    for entry in entries:
        candidate = choose_match(entry, movies)
        db.add(
            Match(
                lb_entry_id=entry.id,
                plex_movie_id=candidate.plex_movie_id,
                confidence=candidate.confidence,
                match_method=candidate.match_method,
                matched_at=now,
                reviewed=False,
            )
        )
    db.commit()
    return len(entries)
