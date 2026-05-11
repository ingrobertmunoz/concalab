# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CONCALAB-UASD** is the official website of the Quality Control of Laboratories program at the Universidad Autónoma de Santo Domingo (UASD), Dominican Republic. It manages proficiency testing (ensayos de aptitud) for clinical laboratories following ISO 13528:2022.

## Tech Stack

- **Pure static site** — no build process, no npm, no framework. HTML5 + CSS3 + Vanilla JS (ES6+).
- **Plotly.js** for interactive data visualizations in proficiency test reports.
- **Firebase** (Firestore + Auth + Analytics) for the results submission form (`resultados.html`).
- **Deployed via** GitHub Pages (primary, `master` branch root) and Firebase Hosting (alternative).

## Running Locally

No server required for most pages — open `index.html` directly in a browser.

For Firebase-dependent features (results form authentication, Firestore writes):
```bash
firebase serve
```

Deploy to Firebase Hosting:
```bash
firebase deploy --only hosting
```

Deploy to GitHub Pages:
```bash
git push origin master   # GitHub Pages auto-updates from master/root
```

## Python Data Pipeline

Scripts run locally to process proficiency test data. They require a `concalab` conda environment:

```bash
conda activate concalab
python scripts/extract_excel_to_csv.py   # Excel → CSV
python scripts/anonymize_data.py          # Anonymize lab identifiers
python scripts/calculate_zscore.py        # Compute Z-Scores (ISO 13528 Algorithm A)
python scripts/generate_report.py         # Generate HTML report with Plotly charts
```

Data flow:
```
Excel (raw) → ensayos_aptitud_consolidado.csv → ensayos_con_zscore.csv → data/informes/EA-XXX-YYYY.json + publicaciones/informes/EA-XXX-YYYY.html
```

## Architecture

### CSS Design System (`css/main.css`)
All colors, shadows, and transitions are defined as CSS variables. Always use them — never hardcode values.

| Variable | Value | Use |
|---|---|---|
| `--primary-color` | `#003f87` | UASD blue — nav, headers, links |
| `--secondary-color` | `#fdb913` | UASD gold — CTAs, accents |
| `--success-color` | `#28a745` | Satisfactory Z-Score |
| `--error-color` | `#dc3545` | Unsatisfactory Z-Score |

Grid layouts: `.grid-2`, `.grid-3`, `.grid-4`. Cards: `.card`. Buttons: `.btn-primary` (gold), `.btn-secondary` (white outline), `.btn-outline` (blue outline).

### JavaScript Modules (`js/`)
- `firebase-config.js` — initializes Firebase app and exports `db`, `auth`, `doc`, `getDoc`, and SDK functions
- `results-form.js` — authenticated form for lab result submission; imports from `firebase-config.js`
- `charts.js` — Plotly rendering for proficiency test visualizations
- `main.js` — global nav, dropdowns, hamburger menu
- `search.js` — in-page content indexer and search UI
- `scroll-reveal.js` — IntersectionObserver-based scroll animations

### Results Submission Flow (`resultados.html`)

```
Lab visits resultados.html
  └─ Firebase Auth login (email + password)
       └─ onAuthStateChanged fires
            └─ Loads lab profile from Firestore → collection "laboratorios" / doc {uid}
                 Profile fields: cod_interno, cod_anonimo, nombre, correo, representante
            └─ Form displays lab name + cod_anonimo as read-only (no dropdown)
            └─ Lab fills in: código de ensayo (EA-XXX-YYYY), fecha, analitos
            └─ On submit:
                 1. EmailJS → confirmation email to lab's contact address
                 2. Firestore → collection "resultados_generales" with:
                      - cod_anonimo (e.g. "AG4") ← used in public reports
                      - cod_interno, uid_lab      ← internal traceability
                      - laboratorio (real name)   ← internal only, never published
                      - resultados[]              ← analyte rows
```

**Lab database management (local tooling, never deployed):**
- `support/laboratorios_concalab.xlsx` — master registry: real names, emails, passwords, cod_anonimo. **Never commit.**
- `support/firebase-service-account.json` — Firebase Admin SDK key. **Never commit.**
- `support/generar_laboratorios.py` — regenerates the Excel with unique codes and passwords.
- `scripts/importar_labs_firebase.py` — imports the Excel into Firebase Auth + Firestore.

```bash
# To import labs (requires service account key):
conda activate concalab
python scripts/importar_labs_firebase.py --dry-run  # simulate first
python scripts/importar_labs_firebase.py            # write to Firebase
```

**Anonymization rule:** `cod_anonimo` (2 letters + 1 digit, e.g. `AG4`) is the only lab identifier that appears in public reports. Real names exist only in Firestore (internal) and `support/` files.

### Proficiency Test Reports
Reports follow the naming scheme `EA-XXX-YYYY`. Each report has:
- `data/informes/EA-XXX-YYYY.json` — computed statistics (robust mean, robust SD, Z-Scores per lab per analyte)
- `publicaciones/informes/EA-XXX-YYYY.html` — interactive HTML report with embedded Plotly charts

Z-Score classification: |Z| ≤ 2 → Satisfactory, 2 < |Z| < 3 → Questionable, |Z| ≥ 3 → Unsatisfactory.

## Key Conventions

- **Language:** All content in Spanish (Dominican Republic).
- **No JS/CSS frameworks** — do not introduce React, Vue, Tailwind, Bootstrap, etc.
- **Lab data is always anonymized** in publicly deployed files. Real lab names must never appear in published files.
- **HTML filenames** use lowercase with hyphens (`portal-educativo.html`).
- **`scripts/`** and `support/` directories are excluded from Firebase/GitHub Pages deployment — they are local tooling only.
- **`support/codigos_laboratorios_secretos.md`**, **`support/firebase-service-account.json`**, and **`support/laboratorios_concalab.xlsx`** must never be committed — all are in `.gitignore`.
- When adding new analytes or labs, update `data/laboratorios.json` and `support/analitos.md` as the source of truth. Also update `support/laboratorios_concalab.xlsx` and re-run `scripts/importar_labs_firebase.py`.

## Available Skills

### `frontend-design` (Anthropic)

Installed at `.claude/skills/frontend-design/`. Invoke with `/frontend-design` when building or improving UI components, pages, or layouts.

**When to use:** Any task involving new pages, redesigns, visual polish, or UI components. The skill guides creation of distinctive, production-grade interfaces with a clear aesthetic direction.

**Design decisions already made for this project:**
- Typography: `Playfair Display` (headings) + `IBM Plex Sans` (body) — load via Google Fonts
- Colors: `--primary-color: #003f87` (UASD blue) + `--secondary-color: #fdb913` (UASD gold) — always use CSS variables, never hardcode
- Aesthetic tone: **Academic-institutional / refined** — clean authority, not generic corporate
- Buttons use `border-radius: 8px` (not pill-shaped)
- Cards use a `4px solid transparent` left border that turns gold on hover
- Section titles use a small gold `section-eyebrow` label above the H2
- Stats/impact numbers use the `.stats-band` full-width blue component
