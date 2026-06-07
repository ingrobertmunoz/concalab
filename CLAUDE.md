# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CONCALAB-UASD** is the official website of the Quality Control of Laboratories program at the Universidad Autónoma de Santo Domingo (UASD), Dominican Republic. It manages proficiency testing (ensayos de aptitud) for clinical laboratories following ISO 13528:2022.

## Tech Stack

- **Pure static site** — no build process, no npm, no framework. HTML5 + CSS3 + Vanilla JS (ES6+).
- **Plotly.js** for interactive data visualizations in proficiency test reports.
- **Firebase** (Firestore + Auth + Analytics) for the results submission form (`resultados.html`).
- **EmailJS** for transactional email:
  - `resultados.html` → `template_53vkh45` (confirmación al lab tras enviar resultados)
  - Config: `service_80iwfhm`, `publicKey: FIaxmqBuhcXtmwHAj`
  - `contacto.html` no usa formulario — tiene botones directos mailto/tel y enlace al portal de resultados
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
CONCALAB habilita una ronda
  └─ Edita data/config.json → "habilitado": true, define "codigo" (ej: EA-001-2026)
  └─ git push origin master → GitHub Pages se actualiza automáticamente

Lab entra a resultados.html
  └─ Firebase Auth login (email + contraseña asignada por CONCALAB)
       └─ onAuthStateChanged carga perfil desde Firestore → colección "laboratorios" / doc {uid}
            Campos del perfil: cod_interno, cod_anonimo, nombre, correo, representante, telefono
       └─ El formulario evalúa el estado en este orden:
            1. Sin perfil en Firestore → banner de error, pedir contacto con admin
            2. habilitado=false en config.json → banner informativo con código de próxima ronda
            3. Ya reportó en esta ronda → banner de advertencia, pedir contacto con admin
            4. Todo OK → formulario activo
       └─ Formulario muestra en solo lectura (no editables por el lab):
            - Nombre del laboratorio + cod_anonimo (cargado de Firestore)
            - Código de ensayo EA-XXX-YYYY (cargado de config.json)
       └─ Lab completa: fecha del reporte, tablas de analitos (Química + Uroanálisis)
       └─ Al enviar:
            1. EmailJS → correo de confirmación al email de contacto del lab
            2. Firestore → colección "resultados_generales" con:
                 - cod_anonimo (ej: "AG4") ← único identificador en informes públicos
                 - cod_interno, uid_lab    ← trazabilidad interna
                 - laboratorio            ← nombre real, solo uso interno, nunca publicado
                 - codigo_ensayo          ← tomado de config.json, no del lab
                 - resultados[]           ← filas de analitos
```

**Políticas de negocio implementadas:**
- **Sin edición por el lab** — si un resultado fue enviado con error, el lab contacta al admin y este lo corrige manualmente en Firestore.
- **Sin doble reporte** — Firestore verifica por `uid_lab` + `codigo_ensayo` antes de mostrar el formulario.
- **Código de ensayo controlado por CONCALAB** — el lab nunca escribe el código EA-XXX-YYYY, lo lee de `data/config.json`.

**Para abrir/cerrar una ronda** — editar `data/config.json` y hacer `git push`:
```json
{
  "ronda_activa": {
    "codigo": "EA-001-2026",
    "descripcion": "Primera Ronda de Ensayo de Aptitud 2026",
    "fecha_apertura": "2026-01-01",
    "fecha_cierre": "2026-12-31",
    "habilitado": true
  }
}
```

**Lab database management (local tooling, never deployed):**
- `support/laboratorios_concalab.xlsx` — registro maestro: nombres reales, correos, contraseñas, cod_anonimo. **Nunca commitear.**
- `support/concalab-uasd-64ff4-firebase-adminsdk-fbsvc-c400cdf10b.json` — clave Firebase Admin SDK. **Nunca commitear.**
- `support/generar_laboratorios.py` — **solo para la creación inicial masiva.** Regenera el Excel completo desde cero con códigos anónimos y contraseñas nuevos al azar. **NUNCA usar para cambios puntuales** (invalidaría el login y el código público de todos los labs existentes).
- `scripts/importar_labs_firebase.py` — importa el Excel **completo** a Firebase Auth + Firestore. Pensado para la carga inicial. No sirve para cambiar correos (crearía usuarios duplicados).
- `scripts/actualizar_labs_firebase.py` — **herramienta para cambios puntuales** (alta, correo, datos, contraseña, activar/desactivar) sin tocar el resto de labs. Es la vía recomendada para mantenimiento día a día.

```bash
# Carga inicial masiva (requiere clave de servicio):
conda activate concalab
python scripts/importar_labs_firebase.py --dry-run  # simular primero
python scripts/importar_labs_firebase.py            # escribir en Firebase
```

#### Flujo para editar/actualizar un laboratorio

**Regla de oro:** editar el Excel NO cambia nada en Firebase. El Excel es solo el registro maestro (fuente de verdad). Todo cambio son **dos pasos**: (1) editar el Excel → (2) aplicarlo a Firebase con `scripts/actualizar_labs_firebase.py`.

**Por qué importa la acción correcta:** `correo` y `password` viven en **Firebase Auth** (solo se cambian con `update_user`); `nombre`, `representante`, `telefono`, `cod_anonimo`, `activo` viven en **Firestore** (se cambian actualizando el documento). El `cod_interno` y el `cod_anonimo` no deben cambiar una vez asignados.

Pasos:
1. Cerrar el Excel en LibreOffice (libera el `.~lock`), luego editar `support/laboratorios_concalab.xlsx`.
2. Editar la lista `OPERACIONES` en `scripts/actualizar_labs_firebase.py` (tiene un ejemplo comentado de cada acción).
3. Simular y aplicar:
```bash
conda activate concalab
python scripts/actualizar_labs_firebase.py --dry-run  # revisar
python scripts/actualizar_labs_firebase.py            # aplicar
```
4. Verificar contra Firebase y enviar credenciales nuevas al lab si cambió correo/contraseña.

| Cambio | Editar Excel | Acción en `OPERACIONES` | Dónde escribe |
|---|---|---|---|
| Lab nuevo | Agregar fila (cód. anónimo único) | `crear` | Auth + Firestore |
| Cambiar correo | Celda correo | `cambiar_correo` | Auth + Firestore |
| Nombre / representante / teléfono | Sí | `cambiar_datos` | Firestore (+ display_name en Auth si cambia nombre) |
| Contraseña | Celda contraseña | `cambiar_password` | Auth |
| Desactivar / reactivar | Columna Activo | `desactivar` (`"activo": False/True`) | Auth (`disabled`) + Firestore (`activo`) |

El script localiza cada lab por `cod_interno` (consulta Firestore), por eso **no duplica** usuarios al cambiar correos.

**Regla de anonimización:** `cod_anonimo` (2 letras + 1 dígito, ej: `AG4`) es el único identificador de laboratorio que aparece en informes públicos. Los nombres reales existen solo en Firestore (uso interno) y en archivos `support/` (nunca deployados).

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
