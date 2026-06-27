from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import cast
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from plexsort.models import LetterboxdEntry, LetterboxdList


def scrape_letterboxd_list(db: Session, url: str, name: str | None = None) -> LetterboxdList:
    lb_list = LetterboxdList(
        name=name or url.rstrip("/").split("/")[-1] or "Letterboxd list",
        source_type="url_scrape",
        source_url=url,
        list_kind="watchlist" if "/watchlist" in url else "list",
        last_updated_at=datetime.now(UTC),
        entry_count=0,
    )
    db.add(lb_list)
    db.flush()

    count = 0
    page = 1
    try:
        while True:
            page_url = url if page == 1 else f"{url.rstrip('/')}/page/{page}/"
            response = requests.get(page_url, timeout=30)
            if response.status_code in {429, 503}:
                time.sleep(2)
                response = requests.get(page_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            posters = soup.select("li.poster-container")
            if not posters:
                break

            for poster in posters:
                film_slug = poster.get("data-film-slug")
                film_link = poster.select_one("div.film-poster")
                title = (
                    film_link.get("data-film-name")
                    if film_link is not None and film_link.get("data-film-name")
                    else film_slug
                )
                if not title:
                    continue
                raw_year_value = (
                    film_link.get("data-film-release-year")
                    if film_link is not None
                    else None
                )
                year_value = cast(str | None, raw_year_value)
                count += 1
                db.add(
                    LetterboxdEntry(
                        list_id=lb_list.id,
                        title=title,
                        year=int(year_value) if year_value else None,
                        lb_film_slug=film_slug,
                        lb_film_url=urljoin("https://letterboxd.com", f"/film/{film_slug}/")
                        if film_slug
                        else None,
                        list_position=count,
                    )
                )

            next_link = soup.select_one("a.next")
            if next_link is None:
                break
            page += 1
            time.sleep(1)
    except Exception as exc:
        lb_list.scrape_error = str(exc)

    lb_list.entry_count = count
    db.commit()
    db.refresh(lb_list)
    return lb_list
