
#!/usr/bin/env python3
"""
scripts/build.py
================
Reads publications.yaml and generates:
  generated/publications.json   — machine-readable registry
  generated/bibliography.bib    — BibTeX for all publications
  README.md                     — human-readable index (root)

Run locally:  python scripts/build.py
Run in CI:    called by .github/workflows/build.yml
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[ERROR] Missing dependency: pyyaml. Run: pip install pyyaml")
    sys.exit(1)

ROOT      = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "publications.yaml"
GEN_DIR   = ROOT / "generated"
README    = ROOT / "README.md"

EPISTEMIC_LABELS = {
    "established":   "🟢 Established",
    "derived":       "🔵 Derived",
    "computational": "🟡 Computational",
    "conjectural":   "🟠 Conjectural",
    "exploratory":   "⚪ Exploratory",
}

STATUS_LABELS = {
    "draft":      "Draft",
    "preprint":   "Preprint",
    "published":  "Published",
    "accepted":   "Accepted",
    "archived":   "Archived",
    "superseded": "Superseded",
}


def load_yaml() -> dict:
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fmt_authors(authors: list) -> str:
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} & {authors[1]}"
    return ", ".join(authors[:-1]) + f" & {authors[-1]}"


def fmt_date(date_str) -> str:
    if not date_str:
        return "n.d."
    parts = str(date_str).split("-")
    months = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]
    if len(parts) >= 2:
        return f"{months[int(parts[1])-1]} {parts[0]}"
    return parts[0]


def build_links(pub: dict) -> str:
    parts = []
    ids = pub.get("identifiers", {}) or {}
    lnk = pub.get("links", {}) or {}
    if ids.get("doi"):
        parts.append(f"[📄 DOI](https://doi.org/{ids['doi']})")
    if ids.get("zenodo") and ids.get("zenodo") != ids.get("doi"):
        parts.append(f"[🗄️ Zenodo](https://doi.org/{ids['zenodo']})")
    if ids.get("arxiv"):
        parts.append(f"[📋 arXiv](https://arxiv.org/abs/{ids['arxiv']})")
    if ids.get("osf"):
        osf = ids["osf"]
        url = osf if osf.startswith("http") else f"https://doi.org/{osf}"
        parts.append(f"[🔓 OSF]({url})")
    if lnk.get("researchgate"):
        parts.append(f"[🔬 ResearchGate]({lnk['researchgate']})")
    if lnk.get("github"):
        parts.append(f"[💻 GitHub]({lnk['github']})")
    return " · ".join(parts) if parts else "*Links pending*"


def bibtex_key(pub: dict) -> str:
    """Unique key: last-name + year + topic-slug + seq."""
    last  = pub["authors"][0].split()[-1].lower()
    parts = pub["id"].split("-")   # ['SUN', 'TOPIC', 'YEAR', 'SEQ']
    topic = parts[1].lower() if len(parts) > 1 else "pub"
    seq   = parts[-1]
    year  = str(pub["year"])
    return f"{last}{year}{topic}{seq}"


def to_bibtex(pub: dict) -> str:
    key  = bibtex_key(pub)
    ids  = pub.get("identifiers", {}) or {}
    doi  = ids.get("doi", "")
    lines = [
        f"@article{{{key},",
        f"  title   = {{{pub['title']}}},",
        f"  author  = {{{'  and  '.join(pub['authors'])}}},",
        f"  year    = {{{pub['year']}}},",
        f"  note    = {{{pub['publication_status']} | epistemic: {pub['epistemic_status']}}},",
    ]
    if doi:
        lines.append(f"  doi     = {{{doi}}},")
        lines.append(f"  url     = {{https://doi.org/{doi}}},")
    lines.append("}")
    return "\n".join(lines)


def gen_json(data: dict) -> None:
    out = GEN_DIR / "publications.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
    print(f"  ✓  {out.relative_to(ROOT)}")


def gen_bibtex(publications: list) -> None:
    out = GEN_DIR / "bibliography.bib"
    entries = [to_bibtex(p) for p in publications]
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"% Auto-generated bibliography — {datetime.now(timezone.utc).date()}\n\n")
        f.write("\n\n".join(entries))
        f.write("\n")
    print(f"  ✓  {out.relative_to(ROOT)}")


def gen_readme(data: dict) -> None:
    reg   = data["registry"]
    pubs  = data["publications"]
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = len(pubs)

    by_area: dict[str, list] = defaultdict(list)
    for pub in sorted(pubs, key=lambda p: p.get("date") or "", reverse=True):
        area = (pub.get("research_area") or ["Other"])[0]
        by_area[area].append(pub)

    ep_counts: dict[str, int] = defaultdict(int)
    for pub in pubs:
        ep_counts[pub["epistemic_status"]] += 1

    lines: list[str] = []

    # Header
    lines += [
        "# Publications",
        "",
        f"> **Auto-generated** from `publications.yaml` · "
        f"Last updated: `{now}` · {total} papers",
        "",
        "> ⚠️ **Do not edit README.md directly.**",
        "> Add or update papers in [`publications.yaml`](./publications.yaml) — "
        "README.md is regenerated automatically by GitHub Actions.",
        "",
        "---",
        "",
        "# Research Publications Registry",
        "",
        f"> **Researcher:** [{reg['name']}]({reg.get('website','#')}) "
        f"· ORCID: [{reg['orcid']}](https://orcid.org/{reg['orcid']})",
        f"> **Profiles:** "
        f"[Google Scholar](https://scholar.google.com/citations?user=bmVEc3wAAAAJ) · "
        f"[ResearchGate](https://www.researchgate.net/profile/Scott-Sun-3) · "
        f"[Lens.org](https://www.lens.org/lens/orcid/{reg['orcid']}) · "
        f"[OSF](https://osf.io/caqxh/)",
        "",
        "---",
        "",
    ]

    # Epistemic legend
    lines += [
        "## 🔍 Epistemic Status Legend",
        "",
        "| Label | Meaning |",
        "| :---- | :------ |",
        "| 🟢 Established | Relies on existing mathematical/scientific consensus |",
        "| 🔵 Derived | Derived under explicit stated assumptions |",
        "| 🟡 Computational | Supported primarily by computational verification |",
        "| 🟠 Conjectural | Conjecture / awaiting proof |",
        "| ⚪ Exploratory | Exploratory theoretical framework |",
        "",
        "> **Note:** `publication_status` (preprint/published) ≠ `epistemic_status`.",
        "> A published paper may still be `exploratory`; a preprint may be `computational`.",
        "",
        "---",
        "",
    ]

    # Quick stats
    lines += [
        "## 📊 Quick Stats",
        "",
        "| Metric | Count |",
        "| :----- | ----: |",
        f"| Total publications | **{total}** |",
    ]
    for ep, count in sorted(ep_counts.items()):
        lines.append(f"| {EPISTEMIC_LABELS.get(ep, ep)} | {count} |")
    lines += ["", "---", ""]

    # Table of contents
    lines += ["## 📋 Table of Contents", ""]
    for area in by_area:
        anchor = area.lower().replace(" ", "-").replace("&","").replace(",","").replace("/","")
        anchor = "-".join(filter(None, anchor.split("-")))
        lines.append(f"- [{area}](#{anchor}) ({len(by_area[area])} papers)")
    lines += ["", "---", ""]

    # Papers by area
    lines.append("## 📑 Papers by Research Area")
    lines.append("")

    for area, area_pubs in by_area.items():
        lines += [
            f"### {area}",
            "",
            "| ID | Title | Authors | Date | Pub. Status | Epistemic | Links |",
            "| :- | :---- | :------ | :--- | :---------- | :-------- | :---- |",
        ]
        for pub in area_pubs:
            title_short = pub["title"][:70] + "…" if len(pub["title"]) > 70 else pub["title"]
            ep_label = EPISTEMIC_LABELS.get(pub["epistemic_status"], pub["epistemic_status"])
            lines.append(
                f"| `{pub['id']}` | **{title_short}** | "
                f"{fmt_authors(pub['authors'])} | "
                f"{fmt_date(pub.get('date'))} | "
                f"{STATUS_LABELS.get(pub['publication_status'], pub['publication_status'])} | "
                f"{ep_label} | "
                f"{build_links(pub)} |"
            )
        lines.append("")

        lines += ["<details>", "<summary><b>🔍 View Abstracts & Details</b></summary>", ""]
        for pub in area_pubs:
            ids = pub.get("identifiers", {}) or {}
            ver = pub.get("versions", {}) or {}
            rel = pub.get("relations", {}) or {}
            lines += [
                f"#### `{pub['id']}` — {pub['title']}",
                "",
                f"- **Authors:** {fmt_authors(pub['authors'])}",
                f"- **Date:** {fmt_date(pub.get('date'))}",
                f"- **Type:** {pub['type']}",
                f"- **Publication status:** {pub['publication_status']}",
                f"- **Epistemic status:** {EPISTEMIC_LABELS.get(pub['epistemic_status'], pub['epistemic_status'])}",
            ]
            if ids.get("doi"):
                lines.append(f"- **DOI:** [{ids['doi']}](https://doi.org/{ids['doi']})")
            if ver.get("current"):
                lines.append(f"- **Current version:** {ver['current']}")
            if rel.get("derived_from"):
                lines.append(f"- **Derived from:** {', '.join(f'`{x}`' for x in rel['derived_from'])}")
            if rel.get("related_to"):
                lines.append(f"- **Related to:** {', '.join(f'`{x}`' for x in rel['related_to'])}")
            if pub.get("keywords"):
                lines.append(f"- **Keywords:** {', '.join(pub['keywords'])}")
            lines += [f"- **Abstract:** {pub['abstract'].strip()}", ""]
            if pub.get("notes"):
                lines += [f"> 📝 {pub['notes']}", ""]
        lines += ["</details>", "", "---", ""]

    # BibTeX
    lines += [
        "## 🔖 BibTeX Citations",
        "",
        "Full bibliography: [`generated/bibliography.bib`](./generated/bibliography.bib)",
        "",
    ]
    for pub in sorted(pubs, key=lambda p: p.get("date") or "", reverse=True):
        lines += [
            "<details>",
            f"<summary><code>{pub['id']}</code> — "
            f"{pub['title'][:60]}{'…' if len(pub['title'])>60 else ''}</summary>",
            "",
            "```bibtex",
            to_bibtex(pub),
            "```",
            "",
            "</details>",
            "",
        ]

    # How to add
    lines += [
        "---",
        "",
        "## 🔄 How to Add a Paper",
        "",
        "1. Edit [`publications.yaml`](./publications.yaml)",
        "2. Add a new entry following the schema (see [`schema.json`](./schema.json))",
        "3. Commit and push — GitHub Actions validates, builds, and updates README automatically",
        "",
        "**Required fields:** `id`, `title`, `authors`, `year`, `type`, "
        "`publication_status`, `epistemic_status`, `research_area`, `abstract`, "
        "`identifiers`, `links`",
        "",
        "**ID format:** `SUN-<TOPIC>-<YEAR>-<SEQ>` (e.g. `SUN-HTSIE-2026-002`)",
        "",
        "---",
        "",
        f"*Generated by [`scripts/build.py`](./scripts/build.py) on {now} UTC*",
    ]

    with open(README, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  ✓  {README.relative_to(ROOT)}")


def main() -> None:
    print(f"Loading {YAML_PATH.name} …")
    data = load_yaml()
    pubs = data.get("publications", [])
    print(f"Found {len(pubs)} publications\n")

    GEN_DIR.mkdir(exist_ok=True)
    print("Generating outputs:")
    gen_json(data)
    gen_bibtex(pubs)
    gen_readme(data)
    print(f"\nDone ✓  ({len(pubs)} publications)")


if __name__ == "__main__":
    main()
