# Marcolphus discography import — design

Date: 2026-06-20

## Goal

Import, additively and idempotently, the discography entries from the 2005
"Marcolphus" plain-text Fluke discography into the existing discography models,
**without damaging or deleting any existing data**. The priority is the
**Remixes** section — Fluke's remixes of other artists, many of which the site
does not yet have.

## In scope (sections imported)

* **Fluke** — the primary act.
* **Lucky Monkeys** — an alias of Fluke.
* **Compilation Appearances** — Fluke tracks on Various-Artists compilations,
  soundtracks and games.
* **Collaborations** — 2 Bit Pie (alias), Atlas, Jon Fugler collaborations, Trisco.
* **Remixes** — Fluke remixing other artists (Björk, New Order, Horse, …).

## Out of scope (ignored)

* The **Remixers** summary section (its data is already carried inline by the
  per-release `[Mixers: …]` blocks).
* **Bootlegs**.
* **Unreleased and Rumoured Releases** (the *Amp* single is already on the site).
* **Samples in Fluke songs**.

## Key modelling decisions

* **Fluke's remixes of others** are modelled as a `Release` owned by the
  **original artist** (e.g. Björk), under a "Remixes" `ReleaseType`, with the
  relevant `Track.remixers` set to **Fluke**. The original artists are created as
  ordinary `Artist`s (not Fluke aliases).
* **People who remixed Fluke** (Lionrock, Atlas, Empirion, …), named in the
  inline `[Mixers: …]` blocks of Fluke's own releases, are created as ordinary
  `Artist`s and attached via `Track.remixers` on the relevant Fluke tracks.
* **Compilation Appearances** are modelled as `Release`s owned by a real
  `Artist` named **"Various Artists"**, under a "Compilation Appearances"
  `ReleaseType`, each holding the Fluke track(s) named.
* **Aliases**: Fluke, Lucky Monkeys and 2 Bit Pie resolve to Fluke (alias →
  `primary_artist = Fluke`). The four members (Jon Fugler, Mike Tournier, Mike
  Bryant, Julian Nugent) are recognised as Fluke personnel.
* **Every newly-created artist** keeps the model default `appears_on_homepage =
  False`, so none of the remixers / original artists / Various Artists appear in
  the homepage hero list.

## Matching & safety rules

* Existing releases are matched by **(artist, normalised title, year)**.
* The import is **add-only / fill-blank**: it creates missing editions, tracks
  and remixer credits, and may fill a field that is currently **blank** on an
  existing record, but it **never overwrites a non-empty value and never
  deletes**.
* The import is **idempotent**: a second run makes no further changes.
* Every create and every blank-fill is **reported on the command line**.
  `--dry-run` prints the same proposed changes without writing anything.

## Architecture (mirrors the existing snapshot pipeline)

### Phase 1 — text import

* `apps/discography/parsers/marcolphus.py` — a **pure**, ORM-free,
  section-aware parser turning the text into dataclasses
  (`MarcolphusRelease` / `MarcolphusEdition` / `MarcolphusTrack`).
* `apps/discography/marcolphus_ingest.py` — an idempotent upsert that knows, per
  section, whether the release artist is Fluke/alias or an independent artist,
  applies the matching & safety rules, sets remixer credits, and returns a
  structured **change log**.
* `apps/discography/management/commands/import_marcolphus.py` — takes a
  **filename** argument (a `.txt` file), parses, ingests, prints the change log;
  supports `--dry-run`.

### Phase 2 — MusicBrainz enrichment (separate command)

* `apps/discography/musicbrainz_search.py` — given (artist, title, year,
  formats), **conservatively** searches MusicBrainz release-groups and returns a
  confident match or `None`; resolves `???` catalogue numbers by matching the MB
  release of the same **format** (e.g. Banco de Gaia – Obsidian 12").
* `apps/discography/management/commands/enrich_from_musicbrainz.py` — iterates
  every `Release`, auto-searches, and on a confident match runs the existing
  `sync_editions_for_release()` to pull **all** editions and full tracklists
  (Marcolphus lists only Fluke-relevant tracks). Uncertain matches are skipped
  and written to a report for manual MBID assignment. Honours MusicBrainz's
  1 req/sec + descriptive User-Agent requirements (already enforced by the
  existing client setup).

## Marcolphus text grammar (what the parser handles)

* **Section header**: `::: <Section name> :::…`.
* **Release header**: `Artist: Title<whitespace><type> [<date>]` — type word
  (single / album / compilation / live-in-the-studio album / promo single /
  split single …) and a date in `[]` (`[1988]`, `[Sep 1989]`, `[11 Apr 1994]`,
  `[spring 1990]`); only the 4-digit year is kept.
* **Edition line**: `<media>: <year> <country> (<label>; <catno>) [<notes>]
  <total time>` — media such as `12"`, `7"`, `CD5`, `CD`, `LP`, `CS`, `MC`,
  `CSS`, `2x12"`, `3xLP`, `2xCD`, `CD-R`, `VHS`, `10"`, `CD3`. `??` / `???`
  catalogue or label become blank.
* **Shared tracklist**: a run of consecutive edition lines followed by a single
  tracklist — the tracklist is attached to **each** edition in the run.
* **Track line**: `<m:ss>   <name> (<mix>)` — length optional; the trailing
  parenthetical becomes `mix_info`; `["alt label"]` annotations are dropped;
  `[disc one:]` / `[vinyl one:]` headers are skipped.
* **`[Mixers: X]` block** (inside a Fluke release): `[remixed by NAME]`
  sub-headers assign `Track.remixers` to the listed mixes.
* **Remixes section**: `[Artist: Title]` → release by that artist; **every**
  listed mix is a Fluke remix → `Track.remixers = [Fluke]`.
* **Compilation Appearances**: `[TrackName]` groups, then `[on Various: Comp]`
  → a Various-Artists release holding the named Fluke track(s).
* **Collaborations**: `[Artist: Title]` → release by that artist; trailing
  `[Person: role]` credits map Fluke members to `featured_artists`.

## Testing (TDD, red → green)

* **Parser** (pure, no DB): fixtures per section — release-header variants,
  shared-tracklist run, `[Mixers:]`, Remixes-with-Fluke-credit, comp
  `[on Various:]`, collaboration credits.
* **Ingest**: alias vs independent artist; Fluke-as-remixer; add-only /
  fill-blank / never-overwrite; idempotency; change-log contents; Various
  Artists; new artists stay off the homepage.
* **Phase 2**: MB candidate scoring (confident vs reject) and `???`-by-format
  resolution, with the MusicBrainz client mocked (no network).

## Won't do

* No cover-art byte downloads during Phase 1 (covers arrive via MusicBrainz in
  Phase 2).
* No edits to the local dev sqlite.
* No deletion or overwrite of existing data, ever.
