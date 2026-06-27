from __future__ import annotations

from decimal import Decimal

from plexsort.ingest.lb_csv import entry_payload_from_row


def test_entry_payload_accepts_letterboxd_list_csv_shape() -> None:
    payload = entry_payload_from_row(
        {
            "Rank": "7",
            "Title": "12 Angry Men",
            "LetterboxdURI": "https://letterboxd.com/film/12-angry-men/",
        },
        1,
    )

    assert payload == {
        "title": "12 Angry Men",
        "year": None,
        "lb_film_slug": "12-angry-men",
        "lb_film_url": "https://letterboxd.com/film/12-angry-men/",
        "list_position": 7,
        "lb_rating": None,
    }


def test_entry_payload_accepts_letterboxd_export_csv_shape() -> None:
    payload = entry_payload_from_row(
        {
            "Name": "Moonlight",
            "Year": "2016",
            "Letterboxd URI": "https://letterboxd.com/film/moonlight-2016/",
            "Rating": "4.5",
        },
        3,
    )

    assert payload is not None
    assert payload["title"] == "Moonlight"
    assert payload["year"] == 2016
    assert payload["lb_film_slug"] == "moonlight-2016"
    assert payload["list_position"] == 3
    assert payload["lb_rating"] == Decimal("4.5")
