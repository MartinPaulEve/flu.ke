"""Scrape the full list of 2bitpie.net blog posts from the Wayback Machine.

Uses the CDX index to enumerate every captured post permalink (/YYYY/MM/DD/slug/),
fetches each post's best capture to read its real title, and derives the date from
the URL path. Writes data/wayback_posts.json as [{title, url, date}] sorted newest
first. Run:  uv run python scripts/scrape_wayback_posts.py
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

UA = "flukecms-archive-scraper (martin@eve.gd)"
POST_RE = re.compile(r"^https?://(?:www\.)?2bitpie\.net/(\d{4})/(\d{2})/(\d{2})/([^/?#]+)/?$", re.I)
SITE_SUFFIXES = (" | 2 Bit Pie", " | 2bit", " – 2 Bit Pie", " - 2 Bit Pie")
BAD_TITLES = {"account suspended", "suspended", "2bitpie.net", ""}


def slug_to_title(slug):
    return slug.replace("-", " ").strip().title()


def clean_title(raw, slug):
    if not raw:
        return slug_to_title(slug)
    title = raw.strip()
    # The site separator is " | " only — en/em dashes appear inside real titles.
    if " | " in title:
        title = title.split(" | ")[0].strip()
    for suffix in SITE_SUFFIXES:
        if title.lower().endswith(suffix.lower()):
            title = title[: -len(suffix)].strip()
    if title.lower().startswith("comments on: "):
        title = title[len("comments on: "):].strip()
    if title.lower() in BAD_TITLES:
        return slug_to_title(slug)
    return title


def fetch_title(session, timestamp, original, slug):
    try:
        resp = session.get(
            f"http://web.archive.org/web/{timestamp}id_/{original}", timeout=40
        )
    except requests.RequestException:
        return slug_to_title(slug)
    if resp.status_code != 200:
        return slug_to_title(slug)
    soup = BeautifulSoup(resp.text, "lxml")
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        raw = og["content"]
    else:
        el = soup.select_one("h1.entry-title, h2.entrytitle, h1.posttitle, .posttitle")
        raw = el.get_text(strip=True) if el else (soup.title.string if soup.title else "")
    return clean_title(raw, slug)


def best_capture(captures):
    """Pick the best (timestamp, original): a 200 if any, latest, prefer https."""
    ok = [c for c in captures if c[2] == "200"] or captures
    ok.sort(key=lambda c: (c[1], c[0].startswith("https")), reverse=True)
    return ok[0][0], ok[0][1]


def main():
    session = requests.Session()
    session.headers["User-Agent"] = UA

    cdx = session.get(
        "http://web.archive.org/cdx/search/cdx",
        params={"url": "2bitpie.net*", "output": "json", "fl": "original,timestamp,statuscode",
                "limit": 200000},
        timeout=120,
    ).json()[1:]

    by_path = {}
    for original, ts, status in cdx:
        m = POST_RE.match(original)
        if not m:
            continue
        y, mo, d, slug = m.groups()
        key = (f"{y}-{mo}-{d}", slug.lower())
        by_path.setdefault(key, {"slug": slug, "date": f"{y}-{mo}-{d}", "captures": []})
        by_path[key]["captures"].append((original, ts, status))

    print(f"{len(by_path)} unique posts; fetching titles…")
    posts = []
    for i, (_key, info) in enumerate(sorted(by_path.items()), 1):
        original, ts = best_capture(info["captures"])
        title = fetch_title(session, ts, original, info["slug"])
        posts.append({
            "title": title,
            "url": f"https://www.2bitpie.net/{info['date'].replace('-', '/')}/{info['slug']}/",
            "date": info["date"],
        })
        print(f"  [{i:>2}/{len(by_path)}] {info['date']}  {title}")
        time.sleep(0.4)

    posts.sort(key=lambda p: p["date"], reverse=True)
    out = Path("data/wayback_posts.json")
    out.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(posts)} posts to {out}")


if __name__ == "__main__":
    main()
