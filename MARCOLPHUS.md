# Importing the Marcolphus discography

This imports the 2005 "Marcolphus" plain-text Fluke discography into the site,
adding the entries we don't yet have — in particular Fluke's **remixes** of other
artists. The design is recorded in
[`docs/superpowers/specs/2026-06-20-marcolphus-import-design.md`](docs/superpowers/specs/2026-06-20-marcolphus-import-design.md).

It runs in **two phases**:

1. **Text import** — parse the `.txt` file and upsert releases, editions, tracks
   and remixer credits.
2. **MusicBrainz enrichment** — for every release, pull the full editions and
   tracklists from MusicBrainz (Marcolphus only lists the Fluke-relevant tracks).

## Safety guarantees

* **Add-only / fill-blank.** The import only *creates* missing records and *fills
  fields that are currently blank*. It **never overwrites a non-empty value and
  never deletes anything.**
* **Idempotent.** Running it again makes no further changes.
* **Reviewable.** Every create and blank-fill is printed; `--dry-run` prints the
  same without writing.

Always take a database backup before the first real run.

## Prerequisites

* The source file. `Ingest/` is git-ignored, so copy your `marcolphus.txt` onto
  the server yourself; the command takes its path as an argument.
* For phase 2 only: set `MUSICBRAINZ_CONTACT` (a contact email/URL) in the
  environment — MusicBrainz requires a descriptive User-Agent.

All commands use `uv run ./manage.py …`.

## Phase 1 — text import

Review first, then write:

```bash
# Dry run: prints every release/edition/track/credit it WOULD create or fill.
uv run ./manage.py import_marcolphus /path/to/marcolphus.txt --dry-run

# Real run: same output, but writes (add-only; existing data is never touched).
uv run ./manage.py import_marcolphus /path/to/marcolphus.txt
```

What it does:

* Fluke and Lucky Monkeys releases are owned by Fluke / its aliases (Lucky
  Monkeys, 2 Bit Pie).
* Remixes become releases owned by the **original artist** (Björk, New Order,
  Horse, …) under a **Remixes** section, with the relevant tracks credited to
  **Fluke** as remixer.
* People who remixed Fluke (Lionrock, Atlas, …) and compilation hosts become
  their own artists; compilation appearances are owned by **Various Artists**.
* Every newly-created artist stays **off the homepage**.

A second run should report `Imported 0 releases, 0 editions, 0 tracks …`.

## Phase 2 — MusicBrainz enrichment

Run this only after you're happy with phase 1. It makes hundreds of external API
calls at 1 request/second, so a full run takes roughly **30–60 minutes**.

```bash
# Dry run: shows which releases get a confident MusicBrainz match.
uv run ./manage.py enrich_from_musicbrainz --dry-run

# Full run.
uv run ./manage.py enrich_from_musicbrainz
```

It conservatively matches each release by artist + title, and on a confident
match pulls all editions, full tracklists and cover art, and fills blank (`???`)
catalogue numbers from the MusicBrainz release of the same format. Releases with
no confident match are listed as "need review" and left untouched.

Useful options:

| Option            | Effect                                                        |
| ----------------- | ------------------------------------------------------------- |
| `--artist Fluke`  | Only releases by this local artist name.                      |
| `--slug <slug>`   | Only the single release with this slug.                       |
| `--only-missing`  | Skip releases that already have a MusicBrainz id.             |
| `--limit N`       | Process at most N releases (handy for a first, smaller run).  |
| `--dry-run`       | Report matches without writing.                               |

### Manual matches

For a release the auto-matcher skips, attach a MusicBrainz release-group by hand
once you've found it:

```bash
uv run ./manage.py musicbrainz_import <release-slug> \
    https://musicbrainz.org/release-group/<mbid>
```

## Re-running

Both phases are safe to re-run at any time. The text import is fully idempotent;
the MusicBrainz enrichment re-syncs (updating blanks only) and is a good way to
pick up newly-added MusicBrainz data later. A practical cadence is to re-run
`enrich_from_musicbrainz --only-missing` periodically to catch releases that have
since gained a MusicBrainz entry.
