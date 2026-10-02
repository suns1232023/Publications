
#!/usr/bin/env python3
"""
scripts/link_check.py
=====================
Checks all external URLs in publications.yaml for reachability.

HTTP status classification:
  200–399  → PASS
  400      → FAIL  (bad request)
  401      → REVIEW (auth required — page may exist)
  403      → REVIEW (forbidden — common for ResearchGate/Scholar)
  404      → FAIL  (not found)
  429      → REVIEW (rate-limited — page likely exists)
  5xx      → FAIL  (server error)
  timeout  → REVIEW (network issue, not necessarily dead)

Output: generated/link-status.json
Exit code 0 always (link failures are REVIEW items, not CI blockers).
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[ERROR] Missing dependency: pyyaml. Run: pip install pyyaml")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[ERROR] Missing dependency: requests. Run: pip install requests")
    sys.exit(1)

ROOT      = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "publications.yaml"
GEN_DIR   = ROOT / "generated"
OUT_PATH  = GEN_DIR / "link-status.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PublicationsLinkChecker/1.0; "
        "+https://github.com/suns1232023/Publications)"
    )
}
TIMEOUT = 15   # seconds per request
DELAY   = 1.0  # seconds between requests (be polite)


def classify(status: int | None, error: str | None) -> str:
    """Map HTTP status to PASS / REVIEW / FAIL."""
    if error:
        return "REVIEW"   # network/timeout — not necessarily dead
    if status is None:
        return "REVIEW"
    if 200 <= status <= 399:
        return "PASS"
    if status in (401, 403, 429):
        return "REVIEW"   # auth/rate-limit — page likely exists
    if status == 404:
        return "FAIL"
    if status >= 500:
        return "FAIL"
    return "REVIEW"


def check_url(url: str) -> dict:
    """Perform a HEAD request (fall back to GET) and return result dict."""
    result = {"url": url, "status": None, "error": None, "result": None}
    try:
        resp = requests.head(url, headers=HEADERS, timeout=TIMEOUT,
                             allow_redirects=True)
        # Some servers reject HEAD; retry with GET
        if resp.status_code in (405, 501):
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                                allow_redirects=True, stream=True)
            resp.close()
        result["status"] = resp.status_code
    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"connection_error: {type(e).__name__}"
    except Exception as e:
        result["error"] = f"exception: {type(e).__name__}"

    result["result"] = classify(result["status"], result["error"])
    return result


def collect_urls(publications: list) -> list[dict]:
    """Extract all URLs from publications, deduplicated."""
    seen: set[str] = set()
    items: list[dict] = []

    for pub in publications:
        pub_id = pub.get("id", "UNKNOWN")

        # identifiers → construct full URLs
        ids = pub.get("identifiers", {}) or {}
        if ids.get("doi"):
            url = f"https://doi.org/{ids['doi']}"
            if url not in seen:
                seen.add(url)
                items.append({"pub_id": pub_id, "field": "doi", "url": url})

        if ids.get("zenodo") and ids["zenodo"] != ids.get("doi"):
            url = f"https://doi.org/{ids['zenodo']}"
            if url not in seen:
                seen.add(url)
                items.append({"pub_id": pub_id, "field": "zenodo", "url": url})

        if ids.get("arxiv"):
            url = f"https://arxiv.org/abs/{ids['arxiv']}"
            if url not in seen:
                seen.add(url)
                items.append({"pub_id": pub_id, "field": "arxiv", "url": url})

        if ids.get("osf"):
            osf = ids["osf"]
            url = osf if osf.startswith("http") else f"https://doi.org/{osf}"
            if url not in seen:
                seen.add(url)
                items.append({"pub_id": pub_id, "field": "osf", "url": url})

        # links
        lnk = pub.get("links", {}) or {}
        for field in ("github", "researchgate", "project"):
            url = lnk.get(field)
            if url and url not in seen:
                seen.add(url)
                items.append({"pub_id": pub_id, "field": field, "url": url})

    return items


def main() -> None:
    print(f"Loading {YAML_PATH.name} …")
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    publications = data.get("publications", [])
    url_items    = collect_urls(publications)
    print(f"Found {len(url_items)} unique URLs to check\n")

    results = []
    counts  = {"PASS": 0, "REVIEW": 0, "FAIL": 0}

    for i, item in enumerate(url_items, 1):
        print(f"  [{i:2d}/{len(url_items)}] {item['url'][:70]}", end=" … ", flush=True)
        check = check_url(item["url"])
        verdict = check["result"]
        counts[verdict] += 1

        status_str = str(check["status"]) if check["status"] else check.get("error", "?")
        symbol = {"PASS": "✓", "REVIEW": "⚠", "FAIL": "✗"}[verdict]
        print(f"{symbol} {verdict} ({status_str})")

        results.append({
            "publication_id": item["pub_id"],
            "field":          item["field"],
            "url":            item["url"],
            "http_status":    check["status"],
            "error":          check["error"],
            "result":         verdict,
        })

        if i < len(url_items):
            time.sleep(DELAY)

    # ── Write report ──
    GEN_DIR.mkdir(exist_ok=True)
    report = {
        "generated":    datetime.now(timezone.utc).isoformat(),
        "total_urls":   len(url_items),
        "summary":      counts,
        "note": (
            "403/429/timeout are REVIEW (not FAIL) — "
            "many academic platforms block automated requests."
        ),
        "results": results,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # ── Print summary ──
    print(f"\n{'─'*50}")
    print(f"  PASS:   {counts['PASS']}")
    print(f"  REVIEW: {counts['REVIEW']}  (403/429/timeout — manual check recommended)")
    print(f"  FAIL:   {counts['FAIL']}   (404 / 5xx)")
    print(f"{'─'*50}")
    print(f"Report saved: {OUT_PATH.relative_to(ROOT)}")

    # Exit 0 always — link failures are informational, not CI blockers
    if counts["FAIL"] > 0:
        print(f"\n⚠  {counts['FAIL']} URL(s) returned FAIL status. "
              "Review generated/link-status.json.")


if __name__ == "__main__":
    main()
