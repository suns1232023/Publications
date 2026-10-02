
name: Build Publication Outputs

on:
  push:
    branches: [main, master]
    paths:
      - "publications.yaml"
      - "schema.json"
      - "scripts/build.py"
      - ".github/workflows/build.yml"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  build:
    name: Generate JSON + BibTeX + README
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: pip install pyyaml

      - name: Validate first (fail fast)
        run: |
          pip install jsonschema
          python scripts/validate.py

      - name: Build outputs
        run: python scripts/build.py

      - name: Upload generated artifacts
        uses: actions/upload-artifact@v4
        with:
          name: publication-registry-${{ github.sha }}
          path: |
            generated/publications.json
            generated/bibliography.bib
            README.md
          retention-days: 90
          if-no-files-found: error
