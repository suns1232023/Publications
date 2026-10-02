
# How to Add or Update a Publication

This repository uses an **automated pipeline**: you edit `publications.json`, and GitHub Actions regenerates `README.md` automatically.

> ⚠️ **Never edit `README.md` directly.** Your changes will be overwritten on the next push.

---

## Workflow Overview

```
You edit publications.json
        ↓
git commit & push
        ↓
GitHub Actions triggers (.github/workflows/update_readme.yml)
        ↓
Validates JSON schema
        ↓
Runs scripts/generate_readme.py
        ↓
Commits updated README.md automatically
```

---

## Step-by-Step: Adding a New Paper

1. **Open `publications.json`** in the GitHub editor or locally.

2. **Add a new entry** to the `"publications"` array:

```json
{
  "id":              "sun-my-new-paper-2026",
  "category":        "mathematical-physics",
  "title":           "Full title of the paper",
  "authors":         ["Scott Sun", "Solomon Chen"],
  "date":            "2026-10",
  "status":          "Preprint",
  "abstract":        "One paragraph abstract.",
  "doi":             "10.5281/zenodo.XXXXXXX",
  "zenodo_doi":      "10.5281/zenodo.XXXXXXX",
  "researchgate_url":"https://www.researchgate.net/publication/XXXXXXX",
  "osf_url":         null,
  "arxiv_id":        null,
  "keywords":        ["keyword1", "keyword2", "keyword3"]
}
```

3. **Commit and push** — the workflow runs automatically.

4. **Check the Actions tab** to confirm the README was regenerated.

---

## Field Reference

| Field | Required | Description |
| :---- | :------: | :---------- |
| `id` | ✅ | Unique kebab-case identifier (e.g. `sun-paper-title-2026`) |
| `category` | ✅ | Must match one of the `categories[].id` values |
| `title` | ✅ | Full paper title |
| `authors` | ✅ | Array of author names |
| `date` | ✅ | `YYYY-MM` format |
| `status` | ✅ | `Working Paper`, `Preprint`, `Under Review`, or `Published` |
| `abstract` | ✅ | One-paragraph abstract |
| `doi` | — | Primary DOI (e.g. `10.5281/zenodo.XXXXXXX`) |
| `zenodo_doi` | — | Zenodo-specific DOI if different from `doi` |
| `researchgate_url` | — | Full ResearchGate publication URL |
| `osf_url` | — | OSF project URL |
| `arxiv_id` | — | arXiv ID (e.g. `2605.13171`) |
| `keywords` | — | Array of keyword strings |

Use `null` for any field that is not yet available.

---

## Available Categories

| Category ID | Display Name |
| :---------- | :----------- |
| `quantum-topology` | Quantum Physics & Topological Geometry |
| `ifg` | Information Fractal Geometry (IFG) Framework |
| `emergent-spacetime` | Emergent Spacetime, Fractal Folding & Quantum Gravity |
| `additive-combinatorics` | Additive Combinatorics & Computational Number Theory |
| `mathematical-physics` | Mathematical Physics & Geometric Structures |

To add a new category, add an entry to the `"categories"` array in `publications.json`.

---

## Running Locally

```bash
# Validate JSON and regenerate README
python scripts/generate_readme.py

# Validate JSON only
python -m json.tool publications.json > /dev/null && echo "Valid JSON"
```

---

## Troubleshooting

| Problem | Solution |
| :------ | :------- |
| Workflow fails with "JSON is invalid" | Check `publications.json` for syntax errors (missing comma, unclosed bracket) |
| Workflow fails with "missing field" | Ensure all required fields are present in the new entry |
| Workflow fails with "unknown category" | Check that `category` matches an existing `categories[].id` |
| Workflow fails with "duplicate ID" | Change the `id` field to be unique |
| README not updated after push | Check the Actions tab for errors; try `workflow_dispatch` to trigger manually |
