#!/usr/bin/env python3
"""
scripts/fetch_scholar.py

Fetch a Google Scholar profile via SerpAPI and write publications.json.

Why SerpAPI: Google Scholar blocks direct scraping from data-center IPs
(GitHub Actions runners, most cloud providers). SerpAPI runs Scholar
queries from clean residential infrastructure and returns structured
JSON. The free tier (100 searches/month) is plenty for a weekly run.

Usage:
    SERPAPI_KEY=xxx python scripts/fetch_scholar.py \\
        --user oVm7TyYAAAAJ --out publications.json

Exit codes:
    0  success
    1  missing/bad API key
    2  SerpAPI request failed
    3  fetched profile but parsed zero publications
"""
import argparse
import json
import os
import sys
import time
from typing import Any

import requests

SERPAPI_URL = "https://serpapi.com/search.json"
PAGE_SIZE = 100  # SerpAPI max per Scholar-author page


def fetch_page(api_key: str, user_id: str, start: int = 0) -> dict[str, Any]:
    params = {
        "engine": "google_scholar_author",
        "author_id": user_id,
        "api_key": api_key,
        "hl": "en",
        "num": PAGE_SIZE,
        "start": start,
        "sort": "pubdate",
    }
    resp = requests.get(SERPAPI_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"SerpAPI error: {data['error']}")
    return data


def fetch_all(api_key: str, user_id: str) -> dict[str, Any]:
    first = fetch_page(api_key, user_id, start=0)
    author = first.get("author") or {}
    articles = list(first.get("articles") or [])
    cited_by = first.get("cited_by") or {}

    start = PAGE_SIZE
    while True:
        pagination = first.get("serpapi_pagination") or {}
        if "next" not in pagination and len(articles) < PAGE_SIZE:
            break
        page = fetch_page(api_key, user_id, start=start)
        batch = page.get("articles") or []
        if not batch:
            break
        articles.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
        first = page

    return {"author": author, "articles": articles, "cited_by": cited_by}


def normalize(payload: dict[str, Any]) -> list[dict]:
    pubs: list[dict] = []
    for a in payload["articles"]:
        title = (a.get("title") or "").strip()
        if not title:
            continue
        cb = a.get("cited_by") or {}
        citations = str(cb.get("value", 0) or 0)
        pubs.append({
            "title": title,
            "authors": (a.get("authors") or "").strip(),
            "venue": (a.get("publication") or "").strip(),
            "year": str(a.get("year") or "").strip(),
            "citations": citations,
            "scholar_link": a.get("link") or "",
        })
    pubs.sort(key=lambda p: (int(p["year"]) if p["year"].isdigit() else 0), reverse=True)
    return pubs


def total_cites_from_table(cited_by: dict[str, Any]) -> int | None:
    table = cited_by.get("table") or []
    for row in table:
        cites = row.get("citations")
        if isinstance(cites, dict) and "all" in cites:
            try:
                return int(cites["all"])
            except (TypeError, ValueError):
                pass
    return None


def h_index(cited_by: dict[str, Any]) -> int | None:
    table = cited_by.get("table") or []
    for row in table:
        h = row.get("h_index")
        if isinstance(h, dict) and "all" in h:
            try:
                return int(h["all"])
            except (TypeError, ValueError):
                pass
    return None


def i10_index(cited_by: dict[str, Any]) -> int | None:
    table = cited_by.get("table") or []
    for row in table:
        i = row.get("i10_index")
        if isinstance(i, dict) and "all" in i:
            try:
                return int(i["all"])
            except (TypeError, ValueError):
                pass
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="Google Scholar user id (e.g. oVm7TyYAAAAJ)")
    ap.add_argument("--out", default="publications.json")
    args = ap.parse_args()

    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        print("ERROR: SERPAPI_KEY env var is empty or unset.", file=sys.stderr)
        return 1

    print(f"Fetching Google Scholar profile via SerpAPI: {args.user}", file=sys.stderr)
    try:
        payload = fetch_all(api_key, args.user)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    pubs = normalize(payload)
    if not pubs:
        print("ERROR: 0 publications parsed.", file=sys.stderr)
        return 3

    author = payload["author"]
    cited_by = payload["cited_by"]
    total = total_cites_from_table(cited_by)
    if total is None:
        total = sum(int(p["citations"]) for p in pubs if p["citations"].isdigit())

    data = {
        "updated_at": int(time.time()),
        "user_id": args.user,
        "source": "scholar.google.com (via SerpAPI)",
        "name": author.get("name", ""),
        "affiliation": author.get("affiliations", ""),
        "h_index": h_index(cited_by),
        "i10_index": i10_index(cited_by),
        "total_citations": total,
        "count": len(pubs),
        "publications": pubs,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(
        f"Wrote {len(pubs)} publications · {total} citations · "
        f"h={data['h_index']} · i10={data['i10_index']} → {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
