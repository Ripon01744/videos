#!/usr/bin/env python3
"""
Auto scraper for https://zmaal.net/
Runs via GitHub Actions every 15 minutes.
Uses the WordPress REST API to fetch latest posts (videos) and writes
title / description / link / thumbnail / date to public/data.json.

The Vite/TanStack site serves public/data.json at /data.json and reads it
from the frontend.
"""
from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests


SITE = "https://zmaal.net"
API = f"{SITE}/wp-json/wp/v2/posts"
PER_PAGE = 100
PAGES = 10  # up to 1000 latest posts across all folders/categories
OUTPUT = Path(__file__).resolve().parent.parent / "public" / "data.json"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "application/json",
}



def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_page(page: int) -> list[dict]:
    qs = urlencode({"per_page": PER_PAGE, "page": page, "_embed": "1"})
    url = f"{API}?{qs}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 400:
        # WP returns 400 when page exceeds total pages
        return []
    r.raise_for_status()
    return r.json()


def extract_thumb(post: dict) -> str | None:
    embedded = post.get("_embedded", {})
    media = embedded.get("wp:featuredmedia") or []
    if media and isinstance(media, list):
        m = media[0]
        src = m.get("source_url")
        if src:
            return src
    # fallback: parse first <img src> from content
    content = post.get("content", {}).get("rendered", "")
    match = re.search(r'<img[^>]+src="([^"]+)"', content)
    return match.group(1) if match else None


def slug_from_link(link: str) -> str:
    path = urlparse(link or "").path.strip("/")
    return path.split("/")[-1] if path else ""


MP4_URL_RE = re.compile(
    r'https?://[^\s"\'<>]+?\.mp4(?:\?[^\s"\'<>]*)?',
    re.IGNORECASE,
)


def fetch_video_src(link: str) -> str | None:
    """Load the episode HTML page and extract the direct .mp4 URL."""
    try:
        r = requests.get(link, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=25)
        if r.status_code != 200:
            return None
        html = r.text
    except requests.RequestException:
        return None
    m = MP4_URL_RE.search(html)
    if not m:
        return None
    url = m.group(0)
    # decode HTML entities (&#038; -> &, &amp; -> &)
    return unescape(url).replace("&#038;", "&")



def extract_terms(post: dict) -> tuple[list[str], list[str]]:
    """Return (categories, tags) as lists of term names from _embedded wp:term."""
    cats: list[str] = []
    tags: list[str] = []
    embedded = post.get("_embedded", {})
    term_groups = embedded.get("wp:term") or []
    for group in term_groups:
        if not isinstance(group, list):
            continue
        for t in group:
            name = t.get("name")
            taxonomy = t.get("taxonomy")
            if not name:
                continue
            if taxonomy == "category":
                cats.append(name)
            elif taxonomy == "post_tag":
                tags.append(name)
            else:
                # custom taxonomies (models, ott platforms etc.) treated as tags/folders
                tags.append(name)
    return cats, tags


def normalize(post: dict) -> dict:
    link = post.get("link") or ""
    cats, tags = extract_terms(post)
    return {
        "id": post.get("id"),
        "slug": slug_from_link(link),
        "title": strip_html(post.get("title", {}).get("rendered", "")),
        "description": strip_html(post.get("excerpt", {}).get("rendered", ""))[:500],
        "link": link,
        "thumbnail": extract_thumb(post),
        "date": post.get("date_gmt"),
        "categories": cats,
        "tags": tags,
        "video_src": None,
    }


def enrich_video_sources(items: list[dict], workers: int = 12) -> None:
    """Populate video_src in place, concurrently."""
    todo = [it for it in items if it.get("link")]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_video_src, it["link"]): it for it in todo}
        done = 0
        for fut in as_completed(futures):
            it = futures[fut]
            it["video_src"] = fut.result()
            done += 1
            if done % 25 == 0:
                print(f"[info] enriched {done}/{len(todo)}")


def main() -> int:
    all_posts: list[dict] = []
    for page in range(1, PAGES + 1):
        try:
            batch = fetch_page(page)
        except requests.RequestException as exc:
            print(f"[warn] page {page} failed: {exc}", file=sys.stderr)
            break
        if not batch:
            break
        all_posts.extend(batch)
        print(f"[info] page {page}: {len(batch)} posts")

    items = [normalize(p) for p in all_posts]
    print(f"[info] enriching {len(items)} items with video sources…")
    enrich_video_sources(items)

    # Build folder summary (category/tag -> count)
    folder_counts: dict[str, int] = {}
    for it in items:
        for name in list(it.get("categories") or []) + list(it.get("tags") or []):
            folder_counts[name] = folder_counts.get(name, 0) + 1
    folders = [
        {"name": n, "count": c}
        for n, c in sorted(folder_counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    payload = {
        "source": SITE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "folders": folders,
        "items": items,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Preserve stable ordering (by date desc) so git diffs stay minimal.
    payload["items"].sort(key=lambda x: x.get("date") or "", reverse=True)


    new_json = json.dumps(payload, ensure_ascii=False, indent=2)

    # Skip write if items are unchanged (avoid empty commits every 15 min).
    if OUTPUT.exists():
        try:
            old = json.loads(OUTPUT.read_text(encoding="utf-8"))
            if old.get("items") == payload["items"]:
                print("[info] no changes; keeping existing data.json")
                return 0
        except json.JSONDecodeError:
            pass

    OUTPUT.write_text(new_json, encoding="utf-8")
    print(f"[ok] wrote {len(items)} items -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
