#!/usr/bin/env python3
"""
scripts/fetch_scholar.py

Usage (runs inside GitHub Action):
  python scripts/fetch_scholar.py --user oVm7TyYAAAAJ --out publications.json

Outputs a publications.json file in the repo root.
"""
import argparse
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://scholar.google.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
}

def fetch_profile(user):
    url = f"{BASE}/citations?user={user}&hl=en&pagesize=100"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text

def parse_profile(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".gsc_a_tr")
    pubs = []
    for r in rows:
        # Title and link
        title_tag = r.select_one(".gsc_a_t a")
        title = title_tag.text.strip() if title_tag else ""
        href = title_tag.get("href") if title_tag else None
        link = urljoin(BASE, href) if href else None

        # Authors / venue / year block
        meta_tag = r.select_one(".gsc_a_t .gsc_a_at")
        # Actually Google uses .gs_gray for authors / venue
        grays = r.select(".gsc_a_t .gs_gray")
        authors = grays[0].text.strip() if len(grays) > 0 else ""
        venue = grays[1].text.strip() if len(grays) > 1 else ""
        year_tag = r.select_one(".gsc_a_y .gsc_a_h")
        year = year_tag.text.strip() if year_tag else ""
        # citations
        cite_tag = r.select_one(".gsc_a_c a")
        citations = cite_tag.text.strip() if cite_tag else r.select_one(".gsc_a_c").text.strip()
        citations = citations if citations else "0"

        pubs.append({
            "title": title,
            "authors": authors,
            "venue": venue,
            "year": year,
            "citations": citations,
            "scholar_link": link
        })
    return pubs

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True, help="Google Scholar user id (e.g. oVm7TyYAAAAJ)")
    p.add_argument("--out", default="publications.json")
    args = p.parse_args()

    print("Fetching Google Scholar profile for user:", args.user)
    html = fetch_profile(args.user)
    pubs = parse_profile(html)
    data = {
        "updated_at": int(time.time()),
        "count": len(pubs),
        "publications": pubs
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(pubs)} publications to {args.out}")

if __name__ == "__main__":
    main()
