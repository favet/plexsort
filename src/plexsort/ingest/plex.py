from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from plexsort.config import Settings
from plexsort.jobs import ProgressCallback
from plexsort.models import PlexMovie

PLEX_PAGE_SIZE = 250


def _request_xml(
    settings: Settings,
    path: str,
    params: dict[str, str] | None = None,
) -> ElementTree.Element:
    if not settings.plex_url or not settings.plex_token:
        raise ValueError("PLEX_URL and PLEX_TOKEN must be configured before syncing Plex.")

    merged_params = dict(params or {})
    merged_params["X-Plex-Token"] = settings.plex_token
    response = requests.get(
        urljoin(settings.plex_url.rstrip("/") + "/", path.lstrip("/")),
        params=merged_params,
        timeout=30,
    )
    response.raise_for_status()
    return ElementTree.fromstring(response.content)


def find_library_section_key(settings: Settings) -> str:
    root = _request_xml(settings, "/library/sections/")
    for directory in root.findall("./Directory"):
        if directory.attrib.get("title") == settings.plex_library:
            key = directory.attrib.get("key")
            if key:
                return key
    raise ValueError(f"Plex library section not found: {settings.plex_library}")


def _text_list(video: ElementTree.Element, tag: str) -> list[str]:
    return [item.attrib["tag"] for item in video.findall(f"./{tag}") if item.attrib.get("tag")]


def _first_media_attr(video: ElementTree.Element, attr: str) -> str | None:
    media = video.find("./Media")
    if media is None:
        return None
    value = media.attrib.get(attr)
    return value or None


def _bitrate_kbps(video: ElementTree.Element) -> int | None:
    """Read overall bitrate, trying <Media> then <Part> (Plex varies by version/analysis state)."""
    for element in (video.find("./Media"), video.find("./Media/Part")):
        if element is None:
            continue
        raw = element.attrib.get("bitrate")
        if raw:
            try:
                return int(raw)
            except ValueError:
                pass
    return None


def _rating_id(video: ElementTree.Element, scheme: str) -> str | None:
    prefix = f"{scheme}://"
    for guid in video.findall("./Guid"):
        value = guid.attrib.get("id", "")
        if value.startswith(prefix):
            return value.removeprefix(prefix).split("?")[0]
    return None


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(int(value), tz=UTC)


def movie_from_video(video: ElementTree.Element, synced_at: datetime) -> dict[str, Any]:
    return {
        "plex_rating_key": video.attrib["ratingKey"],
        "title": video.attrib.get("title", ""),
        "title_sort": video.attrib.get("titleSort") or video.attrib.get("title"),
        "year": int(video.attrib["year"]) if video.attrib.get("year") else None,
        "tmdb_id": _rating_id(video, "tmdb"),
        "imdb_id": _rating_id(video, "imdb"),
        "genres": _text_list(video, "Genre"),
        "directors": _text_list(video, "Director"),
        "duration_ms": int(video.attrib["duration"]) if video.attrib.get("duration") else None,
        "bitrate_kbps": _bitrate_kbps(video),
        "resolution": _first_media_attr(video, "videoResolution"),
        "video_codec": _first_media_attr(video, "videoCodec"),
        "audience_rating": video.attrib.get("audienceRating"),
        "rating": video.attrib.get("rating"),
        "content_rating": video.attrib.get("contentRating"),
        "studio": video.attrib.get("studio"),
        "summary": video.attrib.get("summary"),
        "thumb_url": video.attrib.get("thumb"),
        "added_at": _timestamp(video.attrib.get("addedAt")),
        "last_viewed_at": _timestamp(video.attrib.get("lastViewedAt")),
        "view_count": int(video.attrib.get("viewCount", "0")),
        "last_synced_at": synced_at,
    }


def library_videos(settings: Settings, section_key: str) -> list[ElementTree.Element]:
    videos: list[ElementTree.Element] = []
    start = 0
    while True:
        listing = _request_xml(
            settings,
            f"/library/sections/{section_key}/all",
            {
                "X-Plex-Container-Start": str(start),
                "X-Plex-Container-Size": str(PLEX_PAGE_SIZE),
            },
        )
        page_videos = [item for item in listing.findall("./Video") if item.attrib.get("ratingKey")]
        videos.extend(page_videos)

        total_size = int(listing.attrib.get("totalSize", "0"))
        if not page_videos:
            break
        start += len(page_videos)
        if total_size and start >= total_size:
            break
        if len(page_videos) < PLEX_PAGE_SIZE and not total_size:
            break
    return videos


def sync_plex_movies(
    db: Session,
    settings: Settings,
    progress: ProgressCallback | None = None,
) -> int:
    if progress is not None:
        progress(0, None, "plex_library", "Finding Plex movie library")
    section_key = find_library_section_key(settings)
    videos = library_videos(settings, section_key)
    synced_at = datetime.now(UTC)
    total = len(videos)

    # Index existing rows so we can update-in-place and preserve OMDb enrichment.
    existing: dict[str, PlexMovie] = {
        m.plex_rating_key: m for m in db.scalars(select(PlexMovie)).all()
    }
    synced_keys: set[str] = set()

    for index, item in enumerate(videos, start=1):
        rating_key = item.attrib["ratingKey"]
        if progress is not None:
            title = item.attrib.get("title", rating_key)
            progress(index - 1, total, "plex_metadata", f"Fetching metadata for {title}")
        detail = _request_xml(settings, f"/library/metadata/{rating_key}")
        video = detail.find("./Video")
        if video is None:
            continue

        plex_fields = movie_from_video(video, synced_at)
        synced_keys.add(rating_key)

        if rating_key in existing:
            movie = existing[rating_key]
            for key, value in plex_fields.items():
                setattr(movie, key, value)
        else:
            db.add(PlexMovie(**plex_fields))

    # Prune movies that no longer exist in Plex.
    stale_keys = set(existing.keys()) - synced_keys
    if stale_keys:
        db.execute(delete(PlexMovie).where(PlexMovie.plex_rating_key.in_(stale_keys)))

    db.commit()
    if progress is not None:
        progress(total, total, "plex_complete", f"Synced {total} Plex movies")
    return total
