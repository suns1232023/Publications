
#!/usr/bin/env python3
"""
scripts/validate.py
===================
Validates publications.yaml against schema.json.

Checks:
  1. YAML syntax
  2. JSON Schema (Draft 2020-12) — types, required fields, enum values, patterns
  3. Duplicate publication IDs
  4. Cross-reference integrity (relations.derived_from / related_to point to real IDs)
  5. featured_order uniqueness among selected papers
  6. selected=true papers must have featured_order
  7. one_line_contribution length warning (>200 chars)

Exit code 0 = PASS, 1 = FAIL
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

    # ── 2. Duplicate ID check ──────────────────────────────────────────────
    publications = data.get("publications", [])
    ids = [p["id"] for p in publications if isinstance(p, dict) and "id" in p]
    dupes = sorted(set(x for x in ids if ids.count(x) > 1))

    if dupes:
        print(f"\n[FAIL] Duplicate publication IDs detected:")
        for d in dupes:
            print(f"  x  {d}")
        sys.exit(1)

    print("[PASS] No duplicate IDs")

    # ── 3. Cross-reference integrity ───────────────────────────────────────
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

    # ── 4. featured_order uniqueness among selected papers ─────────────────
    selected_pubs = [p for p in publications
                     if isinstance(p, dict) and p.get("selected") is True]
    featured_orders = [p.get("featured_order") for p in selected_pubs
                       if p.get("featured_order") is not None]
    dupe_orders = sorted(set(x for x in featured_orders if featured_orders.count(x) > 1))

    if dupe_orders:
        print(f"\n[FAIL] Duplicate featured_order values among selected papers:")
        for order in dupe_orders:
            culprits = [p["id"] for p in selected_pubs
                        if p.get("featured_order") == order]
            print(f"  x  featured_order={order}: {culprits}")
        sys.exit(1)

    print("[PASS] featured_order uniqueness")

    # ── 5. selected=true must have featured_order ──────────────────────────
    missing_order = [p["id"] for p in selected_pubs
                     if p.get("featured_order") is None]
    if missing_order:
        print(f"\n[FAIL] selected=true but missing featured_order:")
        for pid in missing_order:
            print(f"  x  {pid}")
        sys.exit(1)

    print("[PASS] selected papers have featured_order")

    # ── 6. one_line_contribution length warning ────────────────────────────
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
            print(f"  !  {pid}: {length} characters (max: 200)")
        # Warning only — not a hard failure

    # ── Summary ────────────────────────────────────────────────────────────
    selected_count = len(selected_pubs)
    print(
        f"\n[PASS] All checks passed -- "
        f"{len(publications)} publications, "
        f"{len(id_set)} unique IDs, "
        f"{selected_count} selected for featured display"
    )


if __name__ == "__main__":
    main()
