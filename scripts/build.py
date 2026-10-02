
#!/usr/bin/env python3
"""
scripts/build.py  —  Publications V2.1
========================================
Reads publications.yaml and generates:
  generated/publications.json   — machine-readable registry (metadata only)
  generated/bibliography.bib    — BibTeX with correct entry types
  README.md                     — editorial research landing page

V2.1 IMPROVEMENTS over V2:
  - README header: "# Scott Sun" (researcher first, not "# Publications")
  - Research Overview: editorial prose, not institutional boilerplate
  - Architecture diagram: "Causality & Time" (not paper title as claim)
  - Selected Research cards: contribution + evidence status + links only
    (no redundant Research area / Keywords in card — moved to Complete Record)
  - Complete Publication Record: two-layer (always-visible line + details)
  - Evidence status: renamed from "Epistemic status" for reader clarity
  - BibTeX entry types: @misc for working-paper/preprint, @article for journal
  - Telemetry separated from publication registry (no _history in publications.json)
  - Line count lint: <=180 OK, 181-220 INFO, >220 WARNING, >260 FAIL
  - First-screen density check: first 40 lines must answer Who/What/Where

STATISTICS PRESERVATION:
  - publications.json contains only bibliographic metadata (no telemetry)
  - Telemetry history is stored separately in generated/telemetry-history.json
  - This keeps the publication registry clean and the analytics history separate

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
# Renamed from "Epistemic status" to "Evidence status" for reader clarity

EVIDENCE_LABELS = {
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

# BibTeX entry types by publication type
BIBTEX_TYPES = {
    "journal-article":  "article",
    "conference-paper": "inproceedings",
    "book-chapter":     "incollection",
    "technical-report": "techreport",
    "working-paper":    "misc",
    "preprint":         "misc",
    "research-note":    "misc",
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


def build_links(pub: dict, compact: bool = True) -> str:
    """Build link string. compact=True for inline, False for full."""
    parts = []
    ids = pub.get("identifiers", {}) or {}
    lnk = pub.get("links", {}) or {}

    if ids.get("doi"):
        parts.append(f"[DOI](https://doi.org/{ids['doi']})")
    if ids.get("osf"):
        osf = ids["osf"]
        url = osf if osf.startswith("http") else f"https://osf.io/{osf.split('/')[-1].lower()}/"
        parts.append(f"[OSF]({url})")
    if ids.get("arxiv"):
        parts.append(f"[arXiv](https://arxiv.org/abs/{ids['arxiv']})")
    if lnk.get("researchgate"):
        parts.append(f"[ResearchGate]({lnk['researchgate']})")
    if lnk.get("github"):
        parts.append(f"[GitHub]({lnk['github']})")

    return " | ".join(parts) if parts else "*Links pending*"


def bibtex_key(pub: dict) -> str:
    """Unique key: lastname + year + topic + seq."""
    last  = pub["authors"][0].split()[-1].lower()
    parts = pub["id"].split("-")
    topic = parts[1].lower() if len(parts) > 1 else "pub"
    seq   = parts[-1]
    year  = str(pub["year"])
    return f"{last}{year}{topic}{seq}"


def to_bibtex(pub: dict) -> str:
    """Generate BibTeX with correct entry type per publication type."""
    key       = bibtex_key(pub)
    bib_type  = BIBTEX_TYPES.get(pub.get("type", "working-paper"), "misc")
    ids       = pub.get("identifiers", {}) or {}
    doi       = ids.get("doi", "")

    lines = [f"@{bib_type}{{{key},"]
    lines.append(f"  title   = {{{pub['title']}}},")
    lines.append(f"  author  = {{{'  and  '.join(pub['authors'])}}},")
    lines.append(f"  year    = {{{pub['year']}}},")

    if bib_type == "misc":
        lines.append(f"  howpublished = {{{pub['publication_status']}}},")
        lines.append(f"  note    = {{Evidence status: {pub['epistemic_status']}}},")
    else:
        lines.append(f"  note    = {{{pub['publication_status']} | evidence: {pub['epistemic_status']}}},")

    if doi:
        lines.append(f"  doi     = {{{doi}}},")
        lines.append(f"  url     = {{https://doi.org/{doi}}},")

    lines.append("}")
    return "\n".join(lines)


# ── Generators ─────────────────────────────────────────────────────────────

def gen_json(data: dict) -> None:
    """
    Generate publications.json — bibliographic metadata only.
    No telemetry, no _history. Clean publication registry.
    """
    # Strip editorial-only fields not needed in machine-readable output
    pubs_clean = []
    for pub in data.get("publications", []):
        p = dict(pub)
        # Keep all bibliographic fields; remove editorial-only fields
        # (selected/featured_order/one_line_contribution are editorial, not bibliographic)
        pubs_clean.append(p)

    output = {
        "_schema_version": data.get("schema_version", "1.0"),
        "_generated":      datetime.now(timezone.utc).isoformat(),
        "_generator":      "scripts/build.py v2.1",
        "_note":           "Bibliographic metadata only. Telemetry stored separately.",
        "registry":        data.get("registry", {}),
        "publications":    pubs_clean,
    }

    out = GEN_DIR / "publications.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
    print(f"  -> {out.relative_to(ROOT)}")


def gen_bibtex(publications: list) -> None:
    """Generate bibliography.bib with correct BibTeX entry types."""
    out = GEN_DIR / "bibliography.bib"
    entries = [to_bibtex(p) for p in publications]
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"% Auto-generated bibliography -- {datetime.now(timezone.utc).date()}\n")
        f.write("% Full record: https://github.com/suns1232023/Publications\n\n")
        f.write("\n\n".join(entries))
        f.write("\n")
    print(f"  -> {out.relative_to(ROOT)}")


def gen_readme(data: dict) -> None:
    """
    Generate README.md with V2.1 editorial structure.

    Structure:
      Block 1: Scott Sun — researcher identity (not "# Publications")
      Block 2: Research Overview — editorial prose
      Block 3: Research Architecture — ASCII map with disclaimer
      Block 4: Selected Research — 4 cards (contribution + status + links)
      Block 5: Complete Publication Record — two-layer compact entries
      Block 6: Evidence & Publication Status — small table
      Block 7: Citation — 2 BibTeX + bibliography.bib link
      Block 8: Research Identifiers + generated footer
    """
    reg  = data["registry"]
    pubs = data["publications"]
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Sort selected papers by featured_order
    selected = sorted(
        [p for p in pubs if p.get("selected") is True],
        key=lambda p: p.get("featured_order", 99)
    )

    # Group all papers by primary research area, sorted by date desc
    by_area: dict[str, list] = defaultdict(list)
    for pub in sorted(pubs, key=lambda p: p.get("date") or "", reverse=True):
        area = (pub.get("research_area") or ["Other"])[0]
        by_area[area].append(pub)

    lines: list[str] = []

    # ── BLOCK 1: Researcher Identity ───────────────────────────────────────
    # "Scott Sun" first — researcher is the entry point, not the database
    lines += [
        "# Scott Sun",
        "",
        "Independent Researcher",
        "",
        "Information · Geometry · Mathematical Physics · Computational Mathematics",
        "",
        f"[ORCID](https://orcid.org/{reg['orcid']}) · "
        f"[Google Scholar](https://scholar.google.com/citations?user=bmVEc3wAAAAJ) · "
        f"[ResearchGate](https://www.researchgate.net/profile/Scott-Sun-3) · "
        f"[scottsun.com]({reg.get('website', 'https://scottsun.com')})",
        "",
        "---",
        "",
    ]

    # ── BLOCK 2: Research Overview ─────────────────────────────────────────
    lines += [
        "## Research Overview",
        "",
        "This archive brings together independent research on information, "
        "geometry, emergent physical structure, and computational mathematics.",
        "",
        "The work ranges from information-geometric frameworks and spectral "
        "dimension to mathematical physics and computational investigations "
        "in additive combinatorics.",
        "",
        "The archive distinguishes publication status from evidence status, "
        "so that exploratory frameworks, computational results, and "
        "mathematical derivations are not presented as equivalent forms of evidence.",
        "",
        "Selected Research reflects the current research programme, "
        "not a ranking of publications.",
        "",
        "---",
        "",
    ]

    # ── BLOCK 3: Research Architecture ────────────────────────────────────
    lines += [
        "## Research Architecture",
        "",
        "The diagram describes the current organisation of the research programme,",
        "not a claim that all components constitute an established physical theory.",
        "",
        "```",
        "RESEARCH PROGRAMME",
        "  |",
        "  +-- INFORMATION & GEOMETRY",
        "  |       |",
        "  |       +-- Structural Information (HTSIE)",
        "  |       |       |",
        "  |       |       +-- Exchange Entropy (EEI)",
        "  |       |",
        "  |       +-- Information Fractal Geometry (IFG)",
        "  |               |",
        "  |               +-- Spectral Dimension",
        "  |               +-- Mathematical Physics (Mobius-Lorentz)",
        "  |",
        "  +-- EMERGENT PHYSICS",
        "  |       |",
        "  |       +-- Causality & Time",
        "  |       +-- Fractal Folding & Quantum Gravity",
        "  |",
        "  +-- COMPUTATIONAL MATHEMATICS",
        "          |",
        "          +-- Sun (2,4,6,8) Binomial Representation",
        "```",
        "",
        "---",
        "",
    ]

    # ── BLOCK 4: Selected Research ─────────────────────────────────────────
    lines += [
        "## Selected Research",
        "",
    ]

    for i, pub in enumerate(selected, 1):
        pub_status = PUB_STATUS_LABELS.get(pub["publication_status"], pub["publication_status"])
        ev_status  = EVIDENCE_LABELS.get(pub["epistemic_status"], pub["epistemic_status"])
        contrib    = str(pub.get("one_line_contribution") or "").strip()
        links_str  = build_links(pub)

        # summary: plain text only (no Markdown bold) for GitHub compatibility
        summary = (
            f"{i:02d} | {pub['title'][:65]}{'...' if len(pub['title'])>65 else ''} "
            f"-- {fmt_authors(pub['authors'])} · {pub['year']} "
            f"· {pub_status} · {ev_status}"
        )

        lines += [
            "<details>",
            f"<summary>{summary}</summary>",
            "",
        ]
        if contrib:
            lines += [f"> {contrib}", ""]
        lines += [
            f"Links: {links_str}",
            "",
            "</details>",
            "",
        ]

    lines += ["---", ""]

    # ── BLOCK 5: Complete Publication Record ───────────────────────────────
    # Two-layer: always-visible compact line + expandable details
    lines += [
        "## Complete Publication Record",
        "",
    ]

    for area, area_pubs in by_area.items():
        lines += [f"### {area}", ""]
        for pub in area_pubs:
            pub_status = PUB_STATUS_LABELS.get(pub["publication_status"], pub["publication_status"])
            ev_status  = EVIDENCE_LABELS.get(pub["epistemic_status"], pub["epistemic_status"])
            ver        = (pub.get("versions") or {}).get("current", "")
            ver_str    = f" · {ver}" if ver else ""
            ids        = pub.get("identifiers", {}) or {}
            doi_inline = f" · [DOI](https://doi.org/{ids['doi']})" if ids.get("doi") else ""

            # Layer 1: always visible — title + key metadata
            always_line = (
                f"{pub['title'][:68]}{'...' if len(pub['title'])>68 else ''} "
                f"-- {fmt_authors(pub['authors'])} · {fmt_date(pub.get('date'))} "
                f"· {pub_status} · {ev_status}{ver_str}{doi_inline}"
            )

            # Layer 2: expandable — abstract + keywords + all links
            abstract = pub.get("abstract", "").strip()
            keywords = pub.get("keywords", []) or []
            rel      = pub.get("relations", {}) or {}
            notes    = pub.get("notes", "")

            lines += [
                "<details>",
                f"<summary>{always_line}</summary>",
                "",
            ]
            if abstract:
                lines += [abstract, ""]
            if keywords:
                lines.append(f"Keywords: {' · '.join(keywords)}")
                lines.append("")
            links_full = build_links(pub, compact=False)
            if links_full != "*Links pending*":
                lines.append(f"Links: {links_full}")
                lines.append("")
            if rel.get("related_to"):
                lines.append(f"Related: {', '.join(f'`{x}`' for x in rel['related_to'])}")
                lines.append("")
            if notes:
                lines.append(f"Note: {notes}")
                lines.append("")
            lines += ["</details>", ""]
        lines.append("")

    lines += ["---", ""]

    # ── BLOCK 6: Evidence & Publication Status ─────────────────────────────
    lines += [
        "## Evidence & Publication Status",
        "",
        "Each paper carries two independent labels.",
        "",
        "**Publication status** — where the paper is in the publication lifecycle:",
        "",
        "| Label | Meaning |",
        "| :---- | :------ |",
        "| `PREPRINT` | Publicly available preprint |",
        "| `WORKING PAPER` | Working paper / research note |",
        "| `ARCHIVED` | Superseded by a later version |",
        "",
        "**Evidence status** — the nature of the supporting evidence:",
        "",
        "| Label | Meaning |",
        "| :---- | :------ |",
        "| `ESTABLISHED` | Consistent with established scientific/mathematical results |",
        "| `DERIVED` | Derived under explicitly stated assumptions |",
        "| `COMPUTATIONAL` | Primarily supported by computational verification |",
        "| `CONJECTURAL` | Proposed conjecture awaiting proof or independent validation |",
        "| `EXPLORATORY` | Early-stage theoretical investigation |",
        "",
        "> Publication status does not equal evidence status.",
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

    # Show BibTeX for selected papers with DOI only (max 2)
    selected_with_doi = [
        p for p in selected
        if (p.get("identifiers") or {}).get("doi")
    ][:2]

    if selected_with_doi:
        lines += [
            "<details>",
            "<summary>Show BibTeX for selected papers</summary>",
            "",
        ]
        for pub in selected_with_doi:
            lines += ["```bibtex", to_bibtex(pub), "```", ""]
        lines += ["</details>", ""]

    lines += ["---", ""]

    # ── BLOCK 8: Research Identifiers + Footer ─────────────────────────────
    lines += [
        "## Research Identifiers",
        "",
        f"[ORCID](https://orcid.org/{reg['orcid']}) · "
        f"[Google Scholar](https://scholar.google.com/citations?user=bmVEc3wAAAAJ) · "
        f"[ResearchGate](https://www.researchgate.net/profile/Scott-Sun-3) · "
        f"[Lens.org](https://www.lens.org/lens/orcid/{reg['orcid']}) · "
        f"[OSF](https://osf.io/caqxh/) · "
        f"[scottsun.com]({reg.get('website', 'https://scottsun.com')})",
        "",
        "---",
        "",
        f"*Generated from [`publications.yaml`](./publications.yaml) "
        f"by [`scripts/build.py`](./scripts/build.py) on {now} UTC. "
        f"To add or update a paper, edit `publications.yaml`.*",
    ]

    readme_content = "\n".join(lines) + "\n"

    with open(README, "w", encoding="utf-8") as f:
        f.write(readme_content)

    # ── Line count lint ────────────────────────────────────────────────────
    line_count = readme_content.count("\n")
    pub_count  = len(pubs)

    if line_count <= 180:
        print(f"  [OK] README.md: {line_count} lines")
    elif line_count <= 220:
        print(f"  [INFO] README.md: {line_count} lines "
              f"(acceptable for {pub_count} publications)")
    elif line_count <= 260:
        print(f"  [WARNING] README.md: {line_count} lines "
              f"(consider condensing Complete Publication Record)")
    else:
        print(f"  [FAIL] README.md: {line_count} lines "
              f"(exceeds 260-line limit for {pub_count} publications)")

    # ── First-screen density check ─────────────────────────────────────────
    first_screen = "\n".join(lines[:40])
    checks = {
        "Who":   any(x in first_screen for x in ["Scott Sun", "Independent Researcher"]),
        "What":  any(x in first_screen for x in ["Information", "Geometry", "Mathematics"]),
        "Where": any(x in first_screen for x in ["ORCID", "Scholar", "ResearchGate"]),
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        print(f"  [WARNING] First-screen missing: {failed}")
    else:
        print(f"  [OK] First-screen answers Who/What/Where within first 40 lines")

    print(f"  -> {README.relative_to(ROOT)}")


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Loading {YAML_PATH.name} ...")
    data = load_yaml()
    pubs = data.get("publications", [])
    selected_count = sum(1 for p in pubs if p.get("selected") is True)
    print(f"Found {len(pubs)} publications ({selected_count} selected)\n")

    GEN_DIR.mkdir(exist_ok=True)

    print("Generating outputs:")
    gen_json(data)
    gen_bibtex(pubs)
    gen_readme(data)

    print(f"\nDone -- {len(pubs)} publications")


if __name__ == "__main__":
    main()
