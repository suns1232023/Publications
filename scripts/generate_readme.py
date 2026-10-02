
#!/usr/bin/env python3
"""
scripts/generate_readme.py
==========================
Reads publications.json and auto-generates README.md.

Run locally:   python scripts/generate_readme.py
Run in CI:     called by .github/workflows/update_readme.yml

Design principles:
- publications.json is the SINGLE SOURCE OF TRUTH
- README.md is GENERATED — never edit it manually
- Adding a paper = add one entry to publications.json
"""

import json
import os
from datetime import datetime, timezone
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLICATIONS_JSON = os.path.join(ROOT, "publications.json")
README_PATH = os.path.join(ROOT, "README.md")


def load_publications() -> dict:
    with open(PUBLICATIONS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def format_authors(authors: list) -> str:
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} & {authors[1]}"
    return ", ".join(authors[:-1]) + f" & {authors[-1]}"


def format_date(date_str: str) -> str:
    """Convert '2026-09' → 'Sep 2026', '2026-09-15' → 'Sep 2026'"""
    parts = date_str.split("-")
    year = parts[0]
    if len(parts) >= 2:
        month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                       "Jul","Aug","Sep","Oct","Nov","Dec"]
        month = month_names[int(parts[1]) - 1]
        return f"{month} {year}"
    return year


def status_badge(status: str) -> str:
    badges = {
        "Working Paper":  "![Working Paper](https://img.shields.io/badge/Status-Working_Paper-yellow)",
        "Preprint":       "![Preprint](https://img.shields.io/badge/Status-Preprint-blue)",
        "Under Review":   "![Under Review](https://img.shields.io/badge/Status-Under_Review-orange)",
        "Published":      "![Published](https://img.shields.io/badge/Status-Published-green)",
    }
    return badges.get(status, f"`{status}`")


def build_links(pub: dict) -> str:
    links = []
    if pub.get("doi"):
        links.append(f"[📄 DOI](https://doi.org/{pub['doi']})")
    if pub.get("zenodo_doi") and pub.get("zenodo_doi") != pub.get("doi"):
        links.append(f"[🗄️ Zenodo](https://doi.org/{pub['zenodo_doi']})")
    if pub.get("arxiv_id"):
        links.append(f"[📋 arXiv](https://arxiv.org/abs/{pub['arxiv_id']})")
    if pub.get("researchgate_url"):
        links.append(f"[🔬 ResearchGate]({pub['researchgate_url']})")
    if pub.get("osf_url"):
        links.append(f"[🔓 OSF]({pub['osf_url']})")
    return " · ".join(links) if links else "*Links pending*"


def build_bibtex(pub: dict) -> str:
    first_author_last = pub["authors"][0].split()[-1].lower()
    year = pub["date"].split("-")[0]
    key = f"{first_author_last}{year}{pub['id'].split('-')[-2] if '-' in pub['id'] else 'paper'}"
    doi_line = f"  doi     = {{{pub['doi']}}},\n" if pub.get("doi") else ""
    url_line = f"  url     = {{https://doi.org/{pub['doi']}}},\n" if pub.get("doi") else ""
    return (
        f"@article{{{key},\n"
        f"  title   = {{{pub['title']}}},\n"
        f"  author  = {{{' and '.join(pub['authors'])}}},\n"
        f"  year    = {{{year}}},\n"
        f"  note    = {{{pub['status']}}},\n"
        f"{doi_line}"
        f"{url_line}"
        f"}}"
    )


def generate_readme(data: dict) -> str:
    author = data["author"]
    categories = {c["id"]: c for c in data["categories"]}
    publications = data["publications"]

    # Group by category, sorted by date descending
    by_category = defaultdict(list)
    for pub in sorted(publications, key=lambda p: p["date"], reverse=True):
        by_category[pub["category"]].append(pub)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = len(publications)

    lines = []

    # ── Header ──
    lines += [
        "# Publications",
        "",
        "> **Auto-generated** from `publications.json` · Last updated: "
        f"`{now}` · {total} papers",
        "",
        "> ⚠️ **Do not edit README.md directly.**",
        "> Add or update papers in [`publications.json`](./publications.json) — "
        "README.md is regenerated automatically.",
        "",
        "---",
        "",
        "# Research Publications & Working Papers",
        "",
        f"> **Primary Author:** [{author['name']}]({author['profile_url']}) "
        f"· ORCID: [{author['orcid']}](https://orcid.org/{author['orcid']})",
        f"> **Profiles:** "
        f"[Google Scholar]({author['google_scholar']}) · "
        f"[ResearchGate]({author['researchgate']})",
        "",
        "---",
        "",
    ]

    # ── Quick Stats ──
    status_counts = defaultdict(int)
    for pub in publications:
        status_counts[pub["status"]] += 1

    lines += [
        "## 📊 Quick Stats",
        "",
        "| Metric | Count |",
        "| :----- | ----: |",
        f"| Total publications | **{total}** |",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")
    lines += ["", "---", ""]

    # ── Table of Contents ──
    lines += ["## 📋 Table of Contents", ""]
    for cat_id, pubs in by_category.items():
        cat = categories.get(cat_id, {"title": cat_id, "icon": "📄"})
        anchor = cat["title"].lower().replace(" ", "-").replace("(", "").replace(")", "").replace("&", "").replace(",", "").replace("/", "")
        anchor = "-".join(filter(None, anchor.split("-")))
        lines.append(f"- [{cat['icon']} {cat['title']}](#{anchor}) ({len(pubs)} papers)")
    lines += ["", "---", ""]

    # ── Papers by Category ──
    lines.append("## 📑 Papers by Category")
    lines.append("")

    for cat_id, pubs in by_category.items():
        cat = categories.get(cat_id, {"title": cat_id, "icon": "📄"})
        lines += [
            f"### {cat['icon']} {cat['title']}",
            "",
            "| Title | Authors | Date | Status | Links |",
            "| :---- | :------ | :--- | :----- | :---- |",
        ]
        for pub in pubs:
            title_short = pub["title"][:80] + "…" if len(pub["title"]) > 80 else pub["title"]
            lines.append(
                f"| **{title_short}** | "
                f"{format_authors(pub['authors'])} | "
                f"{format_date(pub['date'])} | "
                f"{pub['status']} | "
                f"{build_links(pub)} |"
            )
        lines.append("")

        # Expandable abstracts
        lines += [
            "<details>",
            "<summary><b>🔍 View Abstracts & Details</b></summary>",
            "",
        ]
        for pub in pubs:
            lines += [
                f"#### {pub['title']}",
                "",
                f"- **Authors:** {format_authors(pub['authors'])}",
                f"- **Date:** {format_date(pub['date'])}",
                f"- **Status:** {pub['status']}",
            ]
            if pub.get("doi"):
                lines.append(f"- **DOI:** [{pub['doi']}](https://doi.org/{pub['doi']})")
            if pub.get("keywords"):
                lines.append(f"- **Keywords:** {', '.join(pub['keywords'])}")
            lines += [
                f"- **Abstract:** {pub['abstract']}",
                "",
            ]
        lines += ["</details>", "", "---", ""]

    # ── Citation Templates ──
    lines += [
        "## 🔖 Citation Templates",
        "",
        "Select a paper to copy its BibTeX entry:",
        "",
    ]
    for pub in sorted(publications, key=lambda p: p["date"], reverse=True):
        lines += [
            f"<details>",
            f"<summary><b>{pub['title'][:70]}{'…' if len(pub['title'])>70 else ''}</b></summary>",
            "",
            "```bibtex",
            build_bibtex(pub),
            "```",
            "",
            "</details>",
            "",
        ]

    # ── Footer ──
    lines += [
        "---",
        "",
        "## 🔄 How to Add a Paper",
        "",
        "1. Edit [`publications.json`](./publications.json)",
        "2. Add a new entry to the `publications` array following the existing schema",
        "3. Commit and push — GitHub Actions will automatically regenerate `README.md`",
        "",
        "**Schema fields:**",
        "```",
        "{",
        '  "id":              "unique-kebab-case-id",',
        '  "category":        "one of the category ids",',
        '  "title":           "Full paper title",',
        '  "authors":         ["Author One", "Author Two"],',
        '  "date":            "YYYY-MM",',
        '  "status":          "Working Paper | Preprint | Under Review | Published",',
        '  "abstract":        "Paper abstract",',
        '  "doi":             "10.xxxx/xxxxx or null",',
        '  "zenodo_doi":      "10.5281/zenodo.xxxxx or null",',
        '  "researchgate_url":"https://... or null",',
        '  "osf_url":         "https://... or null",',
        '  "arxiv_id":        "XXXX.XXXXX or null",',
        '  "keywords":        ["keyword1", "keyword2"]',
        "}",
        "```",
        "",
        "---",
        "",
        f"*Generated by [`scripts/generate_readme.py`](./scripts/generate_readme.py) "
        f"on {now} UTC*",
    ]

    return "\n".join(lines) + "\n"


def main():
    print("Loading publications.json …")
    data = load_publications()
    print(f"Found {len(data['publications'])} publications in "
          f"{len(data['categories'])} categories")

    readme = generate_readme(data)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)

    print(f"README.md written ({len(readme):,} bytes)")
    print("Done ✓")


if __name__ == "__main__":
    main()
