## 1.6.0 (2026-06-06)

### Feat

- **admin**: regenerate OG image and invalidate cache actions
- **cache**: page caching via Redis/Valkey with site + per-page invalidation
- **frontend**: Open Graph meta on every page
- **seo**: generate cover-composited Open Graph images for all content

## 1.5.2 (2026-06-06)

### Fix

- **pages**: render published pages in the main nav by menu_order

## 1.5.1 (2026-06-06)

### Fix

- **discography**: avoid duplicate _like index in lyric slug migration on Postgres

## 1.5.0 (2026-06-06)

### Feat

- **deploy**: drop TLS labels and redirect www to apex at Traefik

## 1.4.0 (2026-06-06)

### Feat

- **deploy**: drop the bundled Traefik; expose gunicorn for a shared Traefik

## 1.3.0 (2026-06-04)

### Feat

- **deploy**: terminate TLS at Traefik with Let's Encrypt

## 1.2.4 (2026-06-04)

### Fix

- **deploy**: route www.fluke.fm through Traefik

## 1.2.3 (2026-06-03)

### Fix

- **nav**: collapse the header into a hamburger menu on mobile

## 1.2.2 (2026-06-03)

### Fix

- **static**: cache-bust CSS/JS with the release version

## 1.2.1 (2026-06-02)

### Fix

- **css**: wrap long titles/filenames instead of overflowing on mobile

## 1.2.0 (2026-06-01)

### Feat

- **resources**: add a snippet explanation shown in resource listings
- **frontend**: staff-only "Edit this page" footer link

### Perf

- **docker**: drop the recursive chown/chmod from the prod build

## 1.1.1 (2026-06-01)

### Fix

- **deploy**: pin Traefik's Docker API version for newer daemons

## 1.1.0 (2026-06-01)

### Feat

- **deploy**: bind-mount the data dir and make the Traefik port configurable
- **resources**: import and publish the legacy album/live-set archives
- **deploy**: production Docker stack (gunicorn + Traefik)
- **settings**: add a production settings module
- **frontend**: generate the homepage hero artist list and link its sections
- **api**: move the API to /discography/api/ with a descriptive root
- **discography**: add homepage flag and reserve the 'api' slug
- serve the public site live with a documented REST API
- **landing**: surface the discography above resources
- **discography**: publish lyric pages and link them from releases
- **discography**: recover lyric bodies from the Web Archive
- **theme**: make the light theme the default, dark opt-in
- **discography**: store track samples under uuid filenames
- **theme**: add persisted light/dark theme toggle
- **discography**: show alias artist in release titles
- **blog**: regenerate_og command to refresh post OG images
- **blog**: clean imported post bodies (share/related cruft + Files URL remap)
- **admin**: rich-text editing for post Body and Excerpt via TinyMCE
- **blog**: comprehensive Wayback post list + reconcile/dedupe
- **blog**: backfill post publish dates/titles from a metadata file
- **resources**: optional link to a blog post, rendered on the page
- remove the homepage scrolling marquee
- support hosting the CMS on a web server (Reclaim/cPanel)
- deploy pipeline for the static site
- SEO and accessibility polish (RSS, JSON-LD, pa11y gate)
- MusicBrainz sync CLI (built now, snapshot stays primary)
- publish flow with dirty-state tracking
- group resources by subcategory and enrich detail metadata
- blog Open Graph images, Wayback recovery and SEO meta
- cinematic black/red design system and templates
- add static site export engine (build_site)
- import legacy media tree and link it to the discography
- import discography from the archived snapshot
- add content models and admin for all sections

### Fix

- **discography**: suffix release title for any non-Fluke artist
- remove scroll-reveal effect and restore visible news titles
- **admin**: stop seo_title help_text breaking admin change forms
- **security**: harden Docker Compose for the local CMS
- **security**: prevent JSON-LD script breakout (stored XSS)

### Refactor

- retire the static site generator
