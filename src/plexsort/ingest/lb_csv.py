from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

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


def import_letterboxd_csv(db: Session, payload: bytes, name: str | None = None) -> LetterboxdList:
    csv_name, csv_payload = _read_csv_bytes(payload)
    text = csv_payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    list_name = name or csv_name.rsplit(".", 1)[0]

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
    for position, row in enumerate(reader, start=1):
        title = row.get("Name") or row.get("Title")
        if not title:
            continue
        year_value = row.get("Year")
        db.add(
            LetterboxdEntry(
                list_id=lb_list.id,
                title=title,
                year=int(year_value) if year_value else None,
                lb_film_url=row.get("Letterboxd URI") or None,
                list_position=position,
                lb_rating=_decimal(row.get("Rating")),
            )
        )
        count += 1

    lb_list.entry_count = count
    db.commit()
    db.refresh(lb_list)
    return lb_list

