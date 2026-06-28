# PlexSort Matching — System Notes

Concise reference for the matching engine, known failure modes, and manual review workflow.
Read this before touching the match queue or the engine.

---

## How the engine works

`src/plexsort/match/engine.py` — `choose_match(entry, movies)` runs four tiers in order:

1. **Exact title + exact year** → `high / exact_title_year`
2. **Exact title + year within ±1** → `medium / exact_title_near_year`
3. **Exact title + either year is NULL** AND only one Plex movie has that normalized title → `medium / exact_title_missing_year`
4. **Fuzzy title (≥0.9 ratio) + year within ±1** → `low / fuzzy_title_year`
5. No match → `none / none`, `plex_movie_id = NULL`

`normalize(title)` order: lowercase → NFKD → strip combining chars → strip leading article (the/a/an) → strip punctuation → collapse spaces.

---

## Root cause of most `confidence=none` entries

**Letterboxd CSV exports omit the year.** All `lb_entries.year` values imported from CSV are `NULL`.

Tier 3 only fires when there is **exactly one** Plex movie with that normalized title. Any film where Plex holds multiple versions (remakes, editions) falls through to `none` even when the title matches, because the engine can't pick between them.

Tier 4 (fuzzy) also requires both years to be non-NULL and close, so it never fires for CSV imports.

---

## Known systematic title mismatches (Letterboxd → Plex)

These recur whenever the matching engine is re-run or lists are re-imported.
The engine will never match them automatically without TMDB IDs or custom rules.

### UK ↔ US release titles
| Letterboxd | Plex |
|---|---|
| Harry Potter and the Philosopher's Stone | Harry Potter and the Sorcerer's Stone |
| Three Colours: Blue / Red / White | Three Colors: Blue / Red / White |
| A Matter of Life and Death | Stairway to Heaven |
| Mad Max 2 | The Road Warrior |

### Plex uses full subtitle where LB uses short title
| Letterboxd | Plex |
|---|---|
| Star Wars | Star Wars: Episode IV - A New Hope |
| The Empire Strikes Back | Star Wars: Episode V - The Empire Strikes Back |
| Return of the Jedi | Star Wars: Episode VI - Return of the Jedi |
| Star Wars: The Force Awakens | Star Wars: Episode VII - The Force Awakens |
| Star Wars: The Last Jedi | Star Wars: Episode VIII - The Last Jedi |
| Dune (slug dune-2021) | Dune: Part One |
| E.T. the Extra-Terrestrial | E.T. |
| F9 | F9: The Fast Saga |
| F1 | F1: The Movie |
| Spy Kids 2: The Island of Lost Dreams | Spy Kids 2: Island of Lost Dreams |
| Spy Kids 3-D: Game Over | Spy Kids 3: Game Over |
| The Fantastic 4: First Steps | The Fantastic Four: First Steps |

### Plex uses different title form
| Letterboxd | Plex |
|---|---|
| Twelve Monkeys | 12 Monkeys |
| Se7en | Seven |
| Life of Brian | Monty Python's Life of Brian |
| Aguirre | Aguirre, the Wrath of God |
| Sunrise: A Song of Two Humans | Sunrise |
| Apur Sansar | The World of Apu |
| Sinécdoque (Spanish) | Synecdoche, New York |
| They Shoot Horses | They Shoot Horses, Don't They? |
| Ri¢hie Ri¢h (special chars) | Richie Rich |

### Same normalized title, multiple Plex versions (resolved by LB slug year hint)
When Plex has both originals and remakes, the LB slug encodes the year:
`batman-1989` → Batman 1989; `the-batman` → The Batman 2022.
Same pattern for: All Quiet on the Western Front, Nosferatu, Solaris, Lilo & Stitch,
How to Train Your Dragon, Girl with the Dragon Tattoo, Father/The Father,
Heat/The Heat, House/The House, Taxi Driver/A Taxi Driver.

---

## Items that will never match (not movies in Plex)

Several Letterboxd list entries are TV series that ended up in the queue:
Squid Game, Loki, WandaVision, Chernobyl, The Queen's Gambit, Adolescence, Stranger Things 5.
These should be manually marked reviewed/unmatched if they appear.

---

## Manual review workflow

### Getting all unmatched entries (API cap is 200, no offset)

Query Postgres directly:
```
docker compose exec -T db psql -U plexsort -d plexsort -c \
"\COPY (SELECT m.id, e.title, e.year, e.lb_film_slug FROM matches m JOIN lb_entries e ON e.id = m.lb_entry_id WHERE m.reviewed = false AND m.confidence = 'none' ORDER BY e.title) TO STDOUT CSV HEADER"
```

### Finding Plex candidates for a title
```
docker compose exec -T db psql -U plexsort -d plexsort -c \
"SELECT id, title, year FROM plex_movies WHERE lower(title) LIKE '%keyword%';"
```

### Patching a match via API
```
PATCH /api/admin/matches/{match_id}
{"plex_movie_id": <int>, "confidence": "high", "match_method": "manual", "reviewed": true, "reviewer_note": "..."}
```
Set `plex_movie_id=null` and `match_method="manual_unmatched"` to mark as confirmed-unmatched.

### Queue state after 2026-06-27 manual review pass
- Started: 357 `confidence=none` entries
- Resolved: 63 (27 ambiguous by slug, 36 title mismatches)
- Remaining: 294 — genuinely not in the Plex library, or TV shows
- All 1,829 `confidence=medium` entries were auto-matched (exact title, year missing)

---

## What would fix this long-term

TMDB IDs: Plex already stores `tmdb_id` and `imdb_id` on movies when available.
Letterboxd film URLs contain the slug which resolves to TMDB via the Letterboxd API
(unavailable) or a TMDB title/year lookup. Once a TMDB key is added, the engine
can do ID-first matching, which handles all the title variants above automatically.
See `PLAN.md` Phase 6 for the deferred TMDB matching branch.
