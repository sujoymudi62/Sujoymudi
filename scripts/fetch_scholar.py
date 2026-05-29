#!/usr/bin/env python3
"""
scripts/fetch_scholar.py

Scrape a Google Scholar profile and write a publications.json file.

Usage (locally or in GitHub Actions):
  python scripts/fetch_scholar.py --user oVm7TyYAAAAJ --out publications.json

Notes
-----
Google Scholar has no public API. This scrapes the public profile page.
It may occasionally hit a CAPTCHA wall; in that case the script exits
non-zero and the existing publications.json is left untouched (so the
site keeps showing the last good data).
"""
import argparse
import json
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://scholar.google.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_profile(user: str) -> str:
    url = f"{BASE}/citations?user={user}&hl=en&pagesize=100"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    body = resp.text
    if "Please show you're not a robot" in body or "/sorry/" in resp.url:
        raise RuntimeError("Google Scholar served a CAPTCHA; try again later.")
    return body


def parse_profile(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".gsc_a_tr")
    pubs: list[dict] = []
    for r in rows:
        title_tag = r.select_one(".gsc_a_t a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        href = title_tag.get("href")
        link = urljoin(BASE, href) if href else None

        grays = r.select(".gsc_a_t .gs_gray")
        authors = grays[0].get_text(strip=True) if len(grays) > 0 else ""
        venue = grays[1].get_text(strip=True) if len(grays) > 1 else ""

        year_tag = r.select_one(".gsc_a_y .gsc_a_h")
        year = year_tag.get_text(strip=True) if year_tag else ""

        cite_tag = r.select_one(".gsc_a_c a")
        if cite_tag:
            citations = cite_tag.get_text(strip=True) or "0"
        else:
            fallback = r.select_one(".gsc_a_c")
            citations = (fallback.get_text(strip=True) if fallback else "") or "0"

        pubs.append({
            "title": title,
            "authors": authors,
            "venue": venue,
            "year": year,
            "citations": citations,
            "scholar_link": link,
        })

    pubs.sort(key=lambda p: (int(p["year"]) if p["year"].isdigit() else 0), reverse=True)
    return pubs


def summary(pubs: list[dict]) -> dict:
    total_citations = 0
    for p in pubs:
        c = p["citations"]
        if c.isdigit():
            total_citations += int(c)
    return {"total_citations": total_citations}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True, help="Google Scholar user id (e.g. oVm7TyYAAAAJ)")
    p.add_argument("--out", default="publications.json")
    args = p.parse_args()

    print(f"Fetching Google Scholar profile for user: {args.user}", file=sys.stderr)
    try:
        html = fetch_profile(args.user)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    pubs = parse_profile(html)
    if not pubs:
        print("ERROR: parsed 0 publications (page layout may have changed).", file=sys.stderr)
        return 3

    data = {
        "updated_at": int(time.time()),
        "user_id": args.user,
        "source": "scholar.google.com",
        "count": len(pubs),
        **summary(pubs),
        "publications": pubs,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(pubs)} publications to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
