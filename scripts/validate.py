
#!/usr/bin/env python3
"""
scripts/validate.py  —  Publications V2.1
==========================================
Validates publications.yaml against schema.json.

Checks (in order):
  1.  YAML syntax
  2.  JSON Schema (Draft 2020-12)
  3.  Duplicate publication IDs
  4.  Duplicate titles
  5.  Cross-reference integrity (relations point to real IDs)
  6.  Version integrity (versions.current must appear in versions.history)
  7.  Selected paper count (<= 4)
  8.  featured_order continuity (must be 1..N with no gaps)
  9.  selected=true papers must have featured_order
  10. selected=true papers must have one_line_contribution
  11. one_line_contribution length warning (>200 chars)

Exit code 0 = PASS (warnings are non-fatal), 1 = FAIL
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[ERROR] Missing dependency: pyyaml. Run: pip install pyyaml")
    sys.exit(1)

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("[ERROR] Missing dependency: jsonschema. Run: pip install jsonschema")
    sys.exit(1)

ROOT        = Path(__file__).resolve().parents[1]
YAML_PATH   = ROOT / "publications.yaml"
SCHEMA_PATH = ROOT / "schema.json"
MAX_SELECTED = 4


def load_yaml(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[ERROR] YAML syntax error in {path.name}:\n  {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)


def load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON syntax error in {path.name}: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {path}")
        sys.exit(1)


def main() -> None:
    print(f"Validating {YAML_PATH.name} against {SCHEMA_PATH.name} ...")

    data   = load_yaml(YAML_PATH)
    schema = load_json(SCHEMA_PATH)

    # ── 1. JSON Schema validation ──────────────────────────────────────────
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))

    if errors:
        print(f"\n[FAIL] {len(errors)} schema validation error(s):\n")
        for err in errors:
            path = " -> ".join(str(x) for x in err.absolute_path) or "(root)"
            print(f"  x  {path}")
            print(f"     {err.message}\n")
        sys.exit(1)

    print("[PASS] JSON Schema validation")

    publications = data.get("publications", [])

    # ── 2. Duplicate ID check ──────────────────────────────────────────────
    ids = [p["id"] for p in publications if isinstance(p, dict) and "id" in p]
    dupes = sorted(set(x for x in ids if ids.count(x) > 1))
    if dupes:
        print(f"\n[FAIL] Duplicate publication IDs:")
        for d in dupes:
            print(f"  x  {d}")
        sys.exit(1)
    print("[PASS] No duplicate IDs")

    # ── 3. Duplicate title check ───────────────────────────────────────────
    titles = [p.get("title", "") for p in publications if isinstance(p, dict)]
    dupe_titles = sorted(set(t for t in titles if titles.count(t) > 1 and t))
    if dupe_titles:
        print(f"\n[FAIL] Duplicate titles detected:")
        for t in dupe_titles:
            print(f"  x  {t[:80]}")
        sys.exit(1)
    print("[PASS] No duplicate titles")

    # ── 4. Cross-reference integrity ───────────────────────────────────────
    id_set = set(ids)
    ref_errors = []
    for pub in publications:
        pub_id    = pub.get("id", "UNKNOWN")
        relations = pub.get("relations", {}) or {}
        for ref_type in ("derived_from", "related_to"):
            for ref_id in (relations.get(ref_type) or []):
                if ref_id not in id_set:
                    ref_errors.append(
                        f"  x  '{pub_id}' -> {ref_type}: '{ref_id}' not found"
                    )
    if ref_errors:
        print(f"\n[FAIL] Cross-reference errors ({len(ref_errors)}):")
        for e in ref_errors:
            print(e)
        sys.exit(1)
    print("[PASS] Cross-reference integrity")

    # ── 5. Version integrity ───────────────────────────────────────────────
    ver_errors = []
    for pub in publications:
        pub_id  = pub.get("id", "UNKNOWN")
        ver     = pub.get("versions", {}) or {}
        current = ver.get("current")
        history = ver.get("history", []) or []
        if current and history:
            history_versions = [h.get("version") for h in history if isinstance(h, dict)]
            if current not in history_versions:
                ver_errors.append(
                    f"  x  '{pub_id}': versions.current='{current}' "
                    f"not found in versions.history {history_versions}"
                )
    if ver_errors:
        print(f"\n[FAIL] Version integrity errors:")
        for e in ver_errors:
            print(e)
        sys.exit(1)
    print("[PASS] Version integrity")

    # ── 6. Selected paper count ────────────────────────────────────────────
    selected_pubs = [p for p in publications
                     if isinstance(p, dict) and p.get("selected") is True]
    if len(selected_pubs) > MAX_SELECTED:
        print(f"\n[FAIL] Too many selected papers: "
              f"{len(selected_pubs)} (maximum: {MAX_SELECTED})")
        for p in selected_pubs:
            print(f"  x  {p['id']}")
        sys.exit(1)
    print(f"[PASS] Selected paper count ({len(selected_pubs)}/{MAX_SELECTED})")

    # ── 7. featured_order continuity ──────────────────────────────────────
    featured_orders = sorted(
        p.get("featured_order") for p in selected_pubs
        if p.get("featured_order") is not None
    )
    expected_orders = list(range(1, len(selected_pubs) + 1))
    if featured_orders != expected_orders:
        print(f"\n[FAIL] featured_order must be continuous 1..{len(selected_pubs)}:")
        print(f"  Expected: {expected_orders}")
        print(f"  Got:      {featured_orders}")
        sys.exit(1)
    print(f"[PASS] featured_order continuity {featured_orders}")

    # ── 8. selected=true must have featured_order ──────────────────────────
    missing_order = [p["id"] for p in selected_pubs if p.get("featured_order") is None]
    if missing_order:
        print(f"\n[FAIL] selected=true but missing featured_order:")
        for pid in missing_order:
            print(f"  x  {pid}")
        sys.exit(1)
    print("[PASS] All selected papers have featured_order")

    # ── 9. selected=true must have one_line_contribution ──────────────────
    missing_contrib = [
        p["id"] for p in selected_pubs
        if not str(p.get("one_line_contribution") or "").strip()
    ]
    if missing_contrib:
        print(f"\n[FAIL] selected=true but missing one_line_contribution:")
        for pid in missing_contrib:
            print(f"  x  {pid}")
        sys.exit(1)
    print("[PASS] All selected papers have one_line_contribution")

    # ── 10. one_line_contribution length warning ───────────────────────────
    warnings = []
    for pub in publications:
        contrib = pub.get("one_line_contribution")
        if contrib:
            length = len(str(contrib).strip())
            if length > 200:
                warnings.append((pub["id"], length))
    if warnings:
        print(f"\n[WARNING] one_line_contribution exceeds 200 characters:")
        for pid, length in warnings:
            print(f"  !  {pid}: {length} chars (max: 200)")

    # ── Summary ────────────────────────────────────────────────────────────
    print(
        f"\n[PASS] All checks passed -- "
        f"{len(publications)} publications, "
        f"{len(id_set)} unique IDs, "
        f"{len(selected_pubs)} selected for featured display"
    )


if __name__ == "__main__":
    main()
