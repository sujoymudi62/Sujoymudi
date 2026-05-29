#!/usr/bin/env python3
"""
scripts/fetch_scholar.py

Fetch a Google Scholar profile and write publications.json.

Uses the `scholarly` library, which rotates user agents and optionally
proxies — substantially more resilient than a raw HTML scrape from a
data-center IP.

Usage:
    python scripts/fetch_scholar.py --user oVm7TyYAAAAJ --out publications.json
    python scripts/fetch_scholar.py --user oVm7TyYAAAAJ --out publications.json --use-free-proxies

Exit codes:
    0  success
    2  Scholar unreachable / blocked / timed out
    3  fetched profile but parsed zero publications
"""
import argparse
import json
import sys
import time
import traceback

from scholarly import scholarly, ProxyGenerator


def configure_proxies() -> bool:
    """Best-effort: try a free proxy pool. Returns True if a proxy was set."""
    pg = ProxyGenerator()
    try:
        if pg.FreeProxies():
            scholarly.use_proxy(pg)
            return True
    except Exception as e:
        print(f"WARN: free proxy setup failed: {e}", file=sys.stderr)
    return False


def fetch_author(user_id: str) -> dict:
    author = scholarly.search_author_id(user_id)
    return scholarly.fill(
        author,
        sections=["basics", "indices", "counts", "publications"],
    )


def normalize_publications(author: dict) -> list[dict]:
    pubs: list[dict] = []
    for p in author.get("publications", []):
        bib = p.get("bib", {}) or {}
        title = bib.get("title", "").strip()
        if not title:
            continue
        authors = bib.get("author", "").strip()
        venue = (bib.get("venue") or bib.get("citation") or "").strip()
        year = str(bib.get("pub_year", "")).strip()
        citations = str(p.get("num_citations", 0))
        link = p.get("pub_url") or p.get("eprint_url")
        if not link:
            cid = p.get("author_pub_id")
            if cid:
                link = f"https://scholar.google.com/citations?view_op=view_citation&hl=en&user={author.get('scholar_id','')}&citation_for_view={cid}"
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="Google Scholar user id (e.g. oVm7TyYAAAAJ)")
    ap.add_argument("--out", default="publications.json")
    ap.add_argument("--use-free-proxies", action="store_true",
                    help="Route requests through free proxy pool (slower but evades blocks).")
    args = ap.parse_args()

    if args.use_free_proxies:
        print("Configuring free proxy pool…", file=sys.stderr)
        if configure_proxies():
            print("Free proxy pool active.", file=sys.stderr)
        else:
            print("No usable free proxies — continuing direct.", file=sys.stderr)

    print(f"Fetching Google Scholar profile: {args.user}", file=sys.stderr)
    try:
        author = fetch_author(args.user)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        return 2

    pubs = normalize_publications(author)
    if not pubs:
        print("ERROR: 0 publications parsed.", file=sys.stderr)
        return 3

    total_cites_field = author.get("citedby") or sum(int(p["citations"]) for p in pubs if p["citations"].isdigit())
    data = {
        "updated_at": int(time.time()),
        "user_id": args.user,
        "source": "scholar.google.com (via scholarly)",
        "name": author.get("name", ""),
        "affiliation": author.get("affiliation", ""),
        "h_index": author.get("hindex"),
        "i10_index": author.get("i10index"),
        "total_citations": total_cites_field,
        "count": len(pubs),
        "publications": pubs,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(pubs)} publications · {total_cites_field} citations · "
          f"h={author.get('hindex')} to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
