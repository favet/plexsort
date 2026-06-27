from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from plexsort.jobs import ProgressCallback
from plexsort.models import LetterboxdEntry, LetterboxdList


def _read_csv_bytes(payload: bytes) -> tuple[str, bytes]:
    if zipfile.is_zipfile(io.BytesIO(payload)):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not names:
                raise ValueError("No CSV files found in Letterboxd zip export.")
            name = names[0]
            return name, archive.read(name)
    return "upload.csv", payload


def _list_kind(name: str) -> str:
    lowered = name.lower().replace("\\", "/")
    if "watchlist" in lowered:
        return "watchlist"
    if "watched" in lowered:
        return "watched"
    if "diary" in lowered:
        return "diary"
    if "ratings" in lowered:
        return "ratings"
    return "list"


def _decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    return Decimal(value)


def _clean_name(name: str) -> str:
    return Path(name).name.rsplit(".", 1)[0]


def _film_slug(url: str | None) -> str | None:
    if not url:
        return None
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "film":
        return parts[1]
    return None


def entry_payload_from_row(row: dict[str, str], position: int) -> dict[str, Any] | None:
    title = row.get("Name") or row.get("Title")
    if not title:
        return None

    year_value = row.get("Year")
    uri = row.get("Letterboxd URI") or row.get("LetterboxdURI") or None
    rank = row.get("Rank")
    return {
        "title": title,
        "year": int(year_value) if year_value else None,
        "lb_film_slug": _film_slug(uri),
        "lb_film_url": uri,
        "list_position": int(rank) if rank else position,
        "lb_rating": _decimal(row.get("Rating")),
    }


def import_letterboxd_csv(
    db: Session,
    payload: bytes,
    name: str | None = None,
    progress: ProgressCallback | None = None,
) -> LetterboxdList:
    csv_name, csv_payload = _read_csv_bytes(payload)
    text = csv_payload.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    list_name = _clean_name(name or csv_name)
    total = len(rows)
    if progress is not None:
        progress(0, total, "csv_parse", f"Parsing {list_name}")

    lb_list = LetterboxdList(
        name=list_name,
        source_type="csv_export",
        source_url=None,
        list_kind=_list_kind(csv_name),
        last_updated_at=datetime.now(UTC),
        entry_count=0,
    )
    db.add(lb_list)
    db.flush()

    count = 0
    for position, row in enumerate(rows, start=1):
        if progress is not None and (position == 1 or position % 100 == 0 or position == total):
            progress(position, total, "csv_import", f"Importing {list_name}")
        entry_payload = entry_payload_from_row(row, position)
        if entry_payload is None:
            continue
        db.add(LetterboxdEntry(list_id=lb_list.id, **entry_payload))
        count += 1

    lb_list.entry_count = count
    db.commit()
    db.refresh(lb_list)
    if progress is not None:
        progress(total, total, "csv_complete", f"Imported {count} entries from {list_name}")
    return lb_list
