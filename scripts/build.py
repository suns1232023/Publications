
#!/usr/bin/env python3
"""
scripts/build.py  —  Publications V2
=====================================
Reads publications.yaml and generates:
  generated/publications.json   — machine-readable registry (with history preservation)
  generated/bibliography.bib    — BibTeX for all publications
  README.md                     — editorial research landing page (V2 structure)

V2 KEY DESIGN CHANGES vs V1:
  - README is a research landing page, not a database dump
  - First screen: researcher identity + research overview (no "Auto-generated" warning)
  - Selected Research section: 4 featured papers with one-line contributions
  - Complete Publication Record: <details> cards grouped by research area
  - BibTeX: only 2-3 entries in README; full bibliography in generated/bibliography.bib
  - "Auto-generated" notice moved to bottom
  - Target: 120-180 lines

STATISTICS PRESERVATION (Sub Task 2):
  - Before writing generated/publications.json, load existing file
  - Merge: new YAML data takes precedence for metadata fields
  - Preserve: telemetry stats, _history snapshots (append-only)
  - Never overwrite historical data with null/empty values

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

# ── Evidence label maps ────────────────────────────────────────────────────

EPISTEMIC_LABELS = {
    "established":   "ESTABLISHED",
    "derived":       "DERIVED",
    "computational": "COMPUTATIONAL",
    "conjectural":   "CONJECTURAL",
    "exploratory":   "EXPLORATORY",
}

PUB_STATUS_LABELS = {
    "draft":      "DRAFT",
    "preprint":   "PREPRINT",
    "published":  "PUBLISHED",
    "accepted":   "ACCEPTED",
    "archived":   "ARCHIVED",
    "superseded": "SUPERSEDED",
}

# ── Helpers ────────────────────────────────────────────────────────────────

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


def build_links_inline(pub: dict) -> str:
    """Build compact inline links for publication cards."""
    parts = []
    ids = pub.get("identifiers", {}) or {}
    lnk = pub.get("links", {}) or {}
    if ids.get("doi"):
        parts.append(f"[DOI](https://doi.org/{ids['doi']})")
    if ids.get("osf"):
        osf = ids["osf"]
        url = osf if osf.startswith("http") else f"https://doi.org/{osf}"
        parts.append(f"[OSF]({url})")
    if lnk.get("researchgate"):
        parts.append(f"[ResearchGate]({lnk['researchgate']})")
    if lnk.get("github"):
        parts.append(f"[GitHub]({lnk['github']})")
    return " | ".join(parts) if parts else "*Links pending*"


def bibtex_key(pub: dict) -> str:
    last  = pub["authors"][0].split()[-1].lower()
    parts = pub["id"].split("-")
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


# ── Statistics Preservation (Sub Task 2) ──────────────────────────────────

def load_existing_generated() -> dict:
    """
    Load existing generated/publications.json to preserve historical stats.
    Returns empty dict if file does not exist.
    """
    json_path = GEN_DIR / "publications.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Could not load existing publications.json: {e}")
            print("[WARNING] Starting fresh — historical stats will not be preserved.")
    return {}


def merge_publication_stats(new_pub: dict, existing_by_id: dict) -> dict:
    """
    Merge new publication data with existing historical stats.

    Preservation rules:
    - All metadata fields from new_pub (from publications.yaml) take precedence
    - EXCEPT: telemetry stats are preserved from existing if new value is null/missing
    - _history is append-only: existing history is always preserved

    Fields preserved from history:
    - telemetry.zenodo_views, zenodo_downloads, last_fetched
    - _history (list of dated snapshots, never overwritten)
    - _stats_snapshot (manually verified stats)
    """
    pub_id   = new_pub.get("id", "")
    existing = existing_by_id.get(pub_id, {})
    merged   = dict(new_pub)  # start with fresh YAML data

    # Preserve telemetry if not present in new data
    existing_telemetry = existing.get("telemetry", {})
    new_telemetry      = merged.get("telemetry", {})
    if existing_telemetry and not new_telemetry:
        merged["telemetry"] = existing_telemetry
        print(f"  [PRESERVE] {pub_id}: telemetry stats preserved from history")

    # Preserve _history (append-only — never overwrite)
    existing_history = existing.get("_history", [])
    merged["_history"] = existing_history

    # Preserve _stats_snapshot (manually verified stats)
    existing_snapshot = existing.get("_stats_snapshot", {})
    if existing_snapshot and not merged.get("_stats_snapshot"):
        merged["_stats_snapshot"] = existing_snapshot
        print(f"  [PRESERVE] {pub_id}: stats snapshot preserved from history")

    return merged


def build_publications_json(data: dict) -> dict:
    """
    Build the output publications.json, merging with existing historical data.
    """
    existing_data = load_existing_generated()

    # Build lookup by ID from existing data
    existing_pubs = existing_data.get("publications", [])
    existing_by_id = {p["id"]: p for p in existing_pubs if isinstance(p, dict) and "id" in p}

    if existing_by_id:
        print(f"  [HISTORY] Found {len(existing_by_id)} existing records to merge with")
    else:
        print("  [HISTORY] No existing records found — starting fresh")

    # Merge each publication
    merged_pubs = []
    for pub in data.get("publications", []):
        merged = merge_publication_stats(pub, existing_by_id)
        merged_pubs.append(merged)

    # Build output
    output = dict(data)
    output["publications"] = merged_pubs
    output["_generated"]   = datetime.now(timezone.utc).isoformat()
    output["_generator"]   = "scripts/build.py v2"

    return output


# ── Generators ─────────────────────────────────────────────────────────────

def gen_json(data: dict) -> None:
    """Generate publications.json with history preservation."""
    print("\nBuilding publications.json (with history preservation):")
    output = build_publications_json(data)

    out = GEN_DIR / "publications.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
    print(f"  -> {out.relative_to(ROOT)}")


def gen_bibtex(publications: list) -> None:
    """Generate bibliography.bib for all publications."""
    out = GEN_DIR / "bibliography.bib"
    entries = [to_bibtex(p) for p in publications]
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"% Auto-generated bibliography -- {datetime.now(timezone.utc).date()}\n")
        f.write("% Full bibliography: https://github.com/suns1232023/Publications\n\n")
        f.write("\n\n".join(entries))
        f.write("\n")
    print(f"  -> {out.relative_to(ROOT)}")


def gen_readme(data: dict) -> None:
    """
    Generate README.md with V2 editorial structure.
    Target: 120-180 lines.
    """
    reg  = data["registry"]
    pubs = data["publications"]
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Sort selected papers by featured_order
    selected = sorted(
        [p for p in pubs if p.get("selected") is True],
        key=lambda p: p.get("featured_order", 99)
    )

    # Group all papers by primary research area
    by_area: dict[str, list] = defaultdict(list)
    for pub in sorted(pubs, key=lambda p: p.get("date") or "", reverse=True):
        area = (pub.get("research_area") or ["Other"])[0]
        by_area[area].append(pub)

    # Count epistemic statuses
    ep_counts: dict[str, int] = defaultdict(int)
    for pub in pubs:
        ep_counts[pub["epistemic_status"]] += 1

    lines: list[str] = []

    # ── BLOCK 1: Research Identity ─────────────────────────────────────────
    lines += [
        "# Research Publications",
        "",
        f"> **Scott Sun** · Independent Researcher",
        f"> Information · Geometry · Mathematical Physics · Computational Mathematics",
        "",
        f"> {len(pubs)} research records · 2026 · "
        f"[ORCID](https://orcid.org/{reg['orcid']}) · "
        f"[Google Scholar](https://scholar.google.com/citations?user=bmVEc3wAAAAJ) · "
        f"[ResearchGate](https://www.researchgate.net/profile/Scott-Sun-3)",
        "",
        "---",
        "",
    ]

    # ── BLOCK 2: Research Overview ─────────────────────────────────────────
    lines += [
        "## Research Overview",
        "",
        "An evolving record of independent research spanning information theory, "
        "mathematical physics, and computational mathematics.",
        "",
        "Selected papers are presented with research context, publication status, "
        "and links to the underlying research record. "
        "This page is intended for academic readers and potential collaborators.",
        "",
        "---",
        "",
    ]

    # ── BLOCK 3: Research Architecture ────────────────────────────────────
    lines += [
        "## Research Architecture",
        "",
        "The diagram below describes the current organisation of the research programme,",
        "not a claim that all components constitute an established physical theory.",
        "",
        "```",
        "INFORMATION & GEOMETRY",
        "  |",
        "  +-- Structural Information (HTSIE)",
        "  |       |",
        "  |       +-- Exchange Entropy (EEI)",
        "  |",
        "  +-- Information Fractal Geometry (IFG)",
        "          |",
        "          +-- Spectral Dimension",
        "          +-- Mathematical Physics (Mobius-Lorentz)",
        "",
        "EMERGENT PHYSICS",
        "  |",
        "  +-- Causality & Time (Why the Past May Be Inaccessible)",
        "",
        "COMPUTATIONAL MATHEMATICS",
        "  |",
        "  +-- Sun (2,4,6,8) Binomial Representation",
        "```",
        "",
        "---",
        "",
    ]

    # ── BLOCK 4: Selected Research ─────────────────────────────────────────
    lines += [
        "## Selected Research",
        "",
        "> Papers selected to represent the current research focus. "
        "Selection reflects the author's assessment of representative work, "
        "not an external quality ranking.",
        "",
    ]

    for i, pub in enumerate(selected, 1):
        pub_status = PUB_STATUS_LABELS.get(pub["publication_status"], pub["publication_status"])
        ep_status  = EPISTEMIC_LABELS.get(pub["epistemic_status"], pub["epistemic_status"])
        contrib    = str(pub.get("one_line_contribution") or "").strip()
        area       = (pub.get("research_area") or [""])[0]

        # summary line is plain text (no Markdown bold) for GitHub compatibility
        summary_line = (
            f"{i:02d} | {pub['title'][:65]}{'...' if len(pub['title'])>65 else ''} "
            f"-- {fmt_authors(pub['authors'])} · {pub['year']} · {pub_status} · {ep_status}"
        )

        lines += [
            "<details>",
            f"<summary>{summary_line}</summary>",
            "",
        ]
        if contrib:
            lines += [f"> {contrib}", ""]
        lines += [
            f"**Research area:** {area}",
            "",
        ]
        if pub.get("keywords"):
            lines.append(f"**Keywords:** {' · '.join(pub['keywords'])}")
            lines.append("")
        lines.append(f"**Links:** {build_links_inline(pub)}")
        lines += ["", "</details>", ""]

    lines += ["---", ""]

    # ── BLOCK 5: Complete Publication Record ───────────────────────────────
    lines += [
        "## Complete Publication Record",
        "",
    ]

    for area, area_pubs in by_area.items():
        lines += [f"### {area}", ""]
        for pub in area_pubs:
            pub_status = PUB_STATUS_LABELS.get(pub["publication_status"], pub["publication_status"])
            ep_status  = EPISTEMIC_LABELS.get(pub["epistemic_status"], pub["epistemic_status"])
            ver        = (pub.get("versions") or {}).get("current", "")
            ver_str    = f" · {ver}" if ver else ""

            summary_line = (
                f"{pub['title'][:70]}{'...' if len(pub['title'])>70 else ''} "
                f"-- {fmt_authors(pub['authors'])} · {fmt_date(pub.get('date'))} "
                f"· {pub_status} · {ep_status}{ver_str}"
            )

            lines += [
                "<details>",
                f"<summary>{summary_line}</summary>",
                "",
                f"**ID:** `{pub['id']}`",
                "",
                f"**Abstract:** {pub['abstract'].strip()}",
                "",
            ]
            if pub.get("keywords"):
                lines.append(f"**Keywords:** {' · '.join(pub['keywords'])}")
                lines.append("")

            ids = pub.get("identifiers", {}) or {}
            if ids.get("doi"):
                lines.append(f"**DOI:** [{ids['doi']}](https://doi.org/{ids['doi']})")
                lines.append("")

            rel = pub.get("relations", {}) or {}
            if rel.get("related_to"):
                lines.append(f"**Related:** {', '.join(f'`{x}`' for x in rel['related_to'])}")
                lines.append("")

            if pub.get("notes"):
                lines.append(f"**Note:** {pub['notes']}")
                lines.append("")

            lines += ["</details>", ""]
        lines.append("")

    lines += ["---", ""]

    # ── BLOCK 6: Research Status ───────────────────────────────────────────
    lines += [
        "## Research Status",
        "",
        "Each paper carries two independent labels:",
        "",
        "**Publication status** — where the paper is in the publication lifecycle:",
        "",
        "| Label | Meaning |",
        "| :---- | :------ |",
        "| `PREPRINT` | Publicly available preprint |",
        "| `WORKING PAPER` | Working paper / research note |",
        "| `ARCHIVED` | Superseded by a later version |",
        "",
        "**Epistemic status** — confidence level of the scientific claims:",
        "",
        "| Label | Meaning |",
        "| :---- | :------ |",
        "| `ESTABLISHED` | Relies on existing mathematical/scientific consensus |",
        "| `DERIVED` | Derived under explicit stated assumptions |",
        "| `COMPUTATIONAL` | Supported primarily by computational verification |",
        "| `CONJECTURAL` | Conjecture / awaiting proof |",
        "| `EXPLORATORY` | Exploratory theoretical framework |",
        "",
        "> **Note:** Publication status does not equal epistemic status.",
        "> A preprint may be `COMPUTATIONAL`; a working paper may be `EXPLORATORY`.",
        "",
        "---",
        "",
    ]

    # ── BLOCK 7: Citation ──────────────────────────────────────────────────
    lines += [
        "## Citation",
        "",
        f"Full bibliography: [`generated/bibliography.bib`](./generated/bibliography.bib)",
        "",
    ]

    # Show BibTeX for selected papers only (max 2)
    selected_with_doi = [p for p in selected if (p.get("identifiers") or {}).get("doi")][:2]
    if selected_with_doi:
        lines += [
            "<details>",
            "<summary>Show BibTeX for selected papers</summary>",
            "",
        ]
        for pub in selected_with_doi:
            lines += [
                "```bibtex",
                to_bibtex(pub),
                "```",
                "",
            ]
        lines += ["</details>", ""]

    lines += ["---", ""]

    # ── BLOCK 8: Research Identifiers + Maintenance ────────────────────────
    lines += [
        "## Research Identifiers",
        "",
        f"[ORCID](https://orcid.org/{reg['orcid']}) · "
        f"[Google Scholar](https://scholar.google.com/citations?user=bmVEc3wAAAAJ) · "
        f"[ResearchGate](https://www.researchgate.net/profile/Scott-Sun-3) · "
        f"[Lens.org](https://www.lens.org/lens/orcid/{reg['orcid']}) · "
        f"[OSF](https://osf.io/caqxh/)",
        "",
        "---",
        "",
        f"*This page is generated from [`publications.yaml`](./publications.yaml) "
        f"by [`scripts/build.py`](./scripts/build.py) on {now} UTC. "
        f"To add or update a paper, edit `publications.yaml` — do not edit README.md directly.*",
    ]

    readme_content = "\n".join(lines) + "\n"

    with open(README, "w", encoding="utf-8") as f:
        f.write(readme_content)

    # Line count check
    line_count = readme_content.count("\n")
    if line_count > 200:
        print(f"  [WARNING] README.md has {line_count} lines (target: 120-180). "
              f"Consider condensing the Complete Publication Record section.")
    elif line_count > 180:
        print(f"  [INFO] README.md has {line_count} lines (approaching 180-line target).")
    else:
        print(f"  [OK] README.md has {line_count} lines (within 120-180 target).")

    print(f"  -> {README.relative_to(ROOT)}")


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Loading {YAML_PATH.name} ...")
    data = load_yaml()
    pubs = data.get("publications", [])
    selected_count = sum(1 for p in pubs if p.get("selected") is True)
    print(f"Found {len(pubs)} publications ({selected_count} selected for featured display)\n")

    GEN_DIR.mkdir(exist_ok=True)

    print("Generating outputs:")
    gen_json(data)
    gen_bibtex(pubs)
    gen_readme(data)

    print(f"\nDone -- {len(pubs)} publications processed")


if __name__ == "__main__":
    main()
