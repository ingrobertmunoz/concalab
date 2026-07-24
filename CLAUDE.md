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
python scripts/extraer_resultados_firebase.py   # Firestore → CSV crudo (rondas ≥ 2026)
python scripts/calculate_zscore.py              # Z-Scores (ISO 13528 Algoritmos A y S)
python scripts/generate_report.py               # Informe HTML con gráficos Plotly
```

Data flow (desde EA-001-2026):
```
Firestore "resultados_generales"
  → support/ensayos_EA-XXX-YYYY.csv          (crudo, sin normalizar, NO commiteado)
  → data/informes/EA-XXX-YYYY-<area>.json    (estadística calculada, sí desplegado)
  → publicaciones/informes/EA-XXX-YYYY.html  (informe público)
```

**Extracción de una ronda — `scripts/extraer_resultados_firebase.py`**

Sustituye a `extract_excel_to_csv.py`: desde EA-001-2026 los laboratorios reportan por el formulario web, así que la fuente es Firestore y no un Excel. Lee la ronda activa de `data/config.json` o acepta `--codigo`.

```bash
python scripts/extraer_resultados_firebase.py                    # ronda activa
python scripts/extraer_resultados_firebase.py --codigo EA-001-2026
```

Aplana `resultados[]` a una fila por laboratorio-analito, con columnas `cod_anonimo, categoria, analito, metodo, instrumento, resultado_raw, unidad_raw, fecha_reporte`. Los valores salen **tal cual los reportó el laboratorio**, sin convertir ni corregir.

**La salida va en `support/`, nunca en `data/`.** `data/` se despliega a GitHub Pages y este CSV lleva `metodo` e `instrumento` en texto libre (ej. `FUJIFILM DRI-CHEMNX700`); con ~37 labs participantes, publicar la relación `cod_anonimo` → modelo de equipo permitiría re-identificar laboratorios y debilitaría el anonimato de los informes. Además son datos crudos sin revisar. El archivo está en `.gitignore` (`support/ensayos_*.csv`) y es regenerable desde Firestore, que es la fuente de verdad. El script aborta si detecta un campo identificable (`laboratorio`, `correo`, `uid_lab`, `cod_interno`…).

Al terminar imprime un **diagnóstico de magnitud**: marca los resultados que se desvían ≥3x de la mediana de su analito. Sirve para detectar antes de calcular nada tres cosas distintas que se ven parecidas —muestra equivocada, error grueso de transcripción, y efecto de método— sin depender del campo de unidad.

**Sobre las unidades:** el campo `unidad_raw` viene sucio (`MG/DL`, `u/l`, códigos de instrumento como `903`). No afecta el cálculo — en el Z-Score solo entra el valor numérico — así que **no se normaliza antes de calcular**. Normalizar a ciegas es contraproducente: enmascara valores anómalos cuya causa real no es la unidad. La unidad canónica se resuelve al generar el informe, solo para mostrar `X*` con una etiqueta coherente.

**Los ceros son nulos, no mediciones — se excluyen al calcular.** Algunos laboratorios escriben `0`, `00` o `0.00` para decir "no realizado". El extractor los conserva (su trabajo es no tocar el dato crudo), pero `cargar()` en `calcular_zscore.py` los descarta y los lista por consola. El criterio es clínico: **ningún analizador devuelve 0.00 de magnesio, HDL, CK o hierro en un suero real**, así que un 0 no puede ser una medición. Las señales de contexto lo confirman — en EA-001-2026, LK9 acompañó su `00` de `instrument='-----'` y DX6 puso `0.00` en solo 2 de sus 26 analitos.

El daño de tratarlos como medición es doble y va en las dos direcciones: (1) el laboratorio recibe un z ≈ −3.5 y una **no conformidad falsa**; (2) el 0 arrastra el X\* y engorda la σ\* del analito, lo que **esconde desviaciones reales de otros participantes**. Ambos efectos se vieron al corregirlo: desaparecieron 4 no conformes falsos (LK9 en CK y Hierro, DX6 en HDL y Magnesio) y apareció uno verdadero — el CK de QV5 pasó de C a I porque, sin el 0 de LK9, la σ\* del analito bajó de 158.3 a 142.2 y la desviación real cruzó el umbral. Los CV mejoraron en los cuatro analitos (Hierro 30.6% → 22.3%, Magnesio 27.0% → 24.5%, CK 29.3% → 25.7%, HDL 27.9% → 26.3%).

**Analitos dependientes del método:** ALP y Lipasa muestran un efecto de método fuerte (los equipos FUJIFILM Dri-Chem leen ~3x más alto que los métodos húmedos). Agruparlos en un solo valor asignado penaliza a ambos grupos a la vez. ISO 13528 admite evaluación por grupo de pares para estos casos.

**Cálculo de Z-Score — `scripts/calcular_zscore.py`**

```bash
python scripts/calcular_zscore.py --codigo EA-001-2026                  # agrupado → JSON
python scripts/calcular_zscore.py --codigo EA-001-2026 --efecto-metodo  # solo diagnóstico
```

Por defecto evalúa **agrupado**: un valor asignado por analito con todos los laboratorios juntos. Escribe `data/informes/<codigo>-quimica.json`. `--efecto-metodo` no escribe nada; compara el resultado agrupado contra el que daría cada plataforma analítica por separado.

**Auditoría de unidades — `scripts/auditar_unidades.py`**

```bash
python scripts/auditar_unidades.py --codigo EA-001-2026
python scripts/auditar_unidades.py --codigo EA-001-2026 --incluir-cuestionables
```

Comprobación obligatoria antes de publicar: verifica si algún laboratorio salió no conforme **por haber reportado en otra unidad** y no por desempeño. Para cada resultado C o I calcula el factor `X* / resultado` y lo contrasta contra conversiones reales de química clínica (mmol/L ↔ mg/dL, µmol/L ↔ mg/dL, g/L ↔ g/dL, y escalas x10/x100/x1000), usando el X\* del grupo de pares cuando corresponde. Clasifica en *error de unidad probable* (el factor coincide **y** la etiqueta declarada lo respalda), *revisar* (coincide el factor pero no la etiqueta) y *desviación analítica*.

Resultado en EA-001-2026: **0 de 55 no conformes se explican por unidad.** Los tres marcados para revisar resultaron ser otra cosa (error de transcripción y coincidencias espurias de factor en laboratorios con sesgo sistemático). Reportar un no conforme que en realidad es un error de unidad sería injusto con el laboratorio, por eso la comprobación se corre siempre.

**Informe preliminar de triaje — `scripts/informe_preliminar.py`**

```bash
python scripts/informe_preliminar.py --codigo EA-001-2026
```

Genera `support/preliminar_<codigo>-quimica.html` (interno, en `.gitignore`): salud por analito ordenada de peor a mejor con una tira de dispersión de Z-Score, laboratorios con desvío sistemático, y el detalle de cada caso atípico con método e instrumento. Es el paso de revisión previo a decidir qué se publica.

**Trampa a vigilar en cada ronda — bimodalidad por plataforma.** Cuando dos plataformas analíticas conviven en un analito con medianas separadas ≥1.5x, el Algoritmo A no converge a un centro único e **infla la σ\***; la ventana de aceptación se ensancha tanto que casi nadie reprueba. Un "todo aceptable" ahí es un **falso negativo**, no un buen resultado. En EA-001-2026 pasó con **ALP** (2.9x: Fujifilm Dri-Chem mediana 1099 vs química húmeda 378) y **LDH** (2.0x, en sentido inverso). Fujifilm lee alto en ALP y bajo en LDH: es química de método, no un desajuste de calibración.

**Evaluación por grupo de pares (ISO 13528 §7).** Los analitos afectados se listan en `ANALITOS_POR_GRUPO_PARES` dentro de `calcular_zscore.py`. La lista es **explícita a propósito**: cambiar la base de evaluación de un analito es una decisión del proveedor del ensayo y debe quedar documentada, no depender de que un umbral se cruce solo. `detectar_bimodales()` actúa como red de seguridad y avisa por consola si aparece un analito bimodal que no esté en la lista (esos se publican como "no concluyentes").

Cada plataforma recibe su propio X\* y σ\*, y el Z-Score se calcula dentro del grupo que corresponde. Un grupo con menos de `N_MINIMO_GRUPO` (8) participantes **no se evalúa**: esos laboratorios salen con clasificación `NE`, se reportan sin Z-Score y no cuentan en los totales. No se anexan al grupo más parecido — evaluarlos contra un método que no es el suyo sería incorrecto.

Efecto en EA-001-2026: ALP pasó de 34 A / 2 C / 0 I (nadie reprobaba) a 31 A / 2 C / 1 I / 2 NE, LDH de 33 A / 0 C / 0 I a 29 A / 2 C / 0 I / 2 NE, y **Gamma GGT** a 24 A / 1 C / 3 I / 2 NE. El CV interno de cada grupo bajó a ~10% (GGT: 15.1% húmeda, 8.3% seca A). Los grupos de química seca quedan con n=8, por debajo del n≥12 que recomienda ISO 13528; el informe lo declara.

**Las etiquetas de grupo no nombran al fabricante.** `plataforma()` devuelve `Química húmeda` / `Química seca (plataforma A)` / `Química seca (plataforma B)`. Ese valor viaja al JSON público dentro de cada laboratorio (`{"id": "QV5", ..., "grupo": "Química húmeda"}`), así que publicar la marca revelaría qué equipo usa cada `cod_anonimo`. Con grupos pequeños —la plataforma B tiene n=2 en EA-001-2026— eso bastaría para re-identificar laboratorios en un mercado local reducido, que es el mismo riesgo por el que `metodo` e `instrumento` no se despliegan. La distinción **seca vs húmeda es la causa real** del efecto de método, de modo que el informe conserva su poder explicativo sin la marca. La correspondencia marca ↔ plataforma vive solo en el código de `plataforma()`, que no se despliega.

**Página pública del informe — no se genera, se clona**

`publicaciones/informes/EA-XXX-YYYY.html` es un armazón estático escrito a mano: hace `fetch` del JSON y dibuja todo con Plotly en el navegador. No hay script que la genere (`generate_report.py` produce otra cosa: `data/reporte_histogramas.html`). Para una ronda nueva se copia la página anterior y se apunta `JSON_URL` al JSON nuevo.

Como el `fetch` no funciona con `file://`, para verla localmente hay que servir el sitio:
```bash
python3 -m http.server 8765     # luego abrir http://localhost:8765/publicaciones/informes/EA-001-2026.html
```

Diferencias de `EA-001-2026.html` respecto a la de 2025, todas necesarias y a conservar en rondas futuras:

- **Identificadores de texto** — el eje usa `cod_anonimo` (`QV5`), no enteros. La de 2025 ordenaba con `sort((a,b) => a-b)`, que sobre texto no ordena.
- **Histograma con rango acotado a |z| ≤ 5** — sin esto un solo resultado extremo estira el eje y mete a todos los demás en una única barra, con lo que el histograma deja de mostrar la distribución. Los laboratorios que caen fuera **no se ocultan**: se dibujan como triángulos `◀ ▶` en el borde hacia el que se salen (con código, resultado y Z-Score en el tooltip) y se nombran en una línea sobre el gráfico, hasta 3 para no desbordar el ancho. Cada laboratorio debe poder localizarse en su propio informe; contar cuántos quedaron fuera no basta.
- **Eje de Z-Score acotado a |z| ≤ 6** — mismo problema: un z de +56 aplasta las otras 36 barras contra el cero. Las barras que exceden se dibujan al tope y conservan su valor real en la etiqueta y el tooltip.
- **Etiquetas selectivas** — solo se rotulan las barras con |z| > 2; rotular las 37 satura el gráfico y entierra justo lo que hay que leer.
- **Aviso de evaluación no concluyente** — lee `evaluacion_confiable` del JSON y sustituye la alerta de CV en los analitos bimodales, para que un "todo aceptable" producto de una σ* inflada no se presente como buen desempeño.
- **Pestañas de área** — Química Clínica activa, Uroanálisis deshabilitada hasta que exista su JSON.
- **Resumen por laboratorio** (tabla ordenable, después del heatmap) — consolida conformes / cuestionables / no conformes por `cod_anonimo`. Dos reglas que **no se deben quitar**: (1) **excluye los analitos no concluyentes** — con una σ* inflada casi todo sale aceptable, así que incluirlos regala puntos de conformidad a todos por igual; (2) **muestra siempre "% de N"** junto al porcentaje, porque cada laboratorio reporta distinta cantidad de analitos (de 8 a 26 en esta ronda) y un 100% sobre 9 no equivale a un 100% sobre 24. Ordena por conformidad descendente, con desempate por cantidad de analitos y luego por código, para que un 100% sobre 9 no quede por encima de un 100% sobre 24.
- **Desempeño global de los laboratorios** (bloque justo debajo de las tarjetas de resumen) — métrica de **laboratorios, no de resultados**: un laboratorio es satisfactorio solo si **ninguno** de sus analitos salió no conforme. En EA-001-2026, 20 de 37 = 54.1%, muy por debajo del 88.0% de resultados aceptables del encabezado, y esa distancia es el punto: un resultado errado que llega a un paciente es una falla sin importar cuántos otros salieron bien. Va **arriba, no al final** — es un titular, y después de 26 gráficas nadie lo lee. Dos piezas que **no se deben quitar**: (1) la **estratificación** (satisfactorio / 1–2 no conformes / ≥3 no conformes), porque el porcentaje solo no distingue una falla aislada de trece; (2) la **nota de concentración**, porque las no conformidades no están repartidas — en esta ronda 6 laboratorios acumulan 39 de los 58 no conformes (67%), y sin decirlo la cifra sugiere un problema generalizado que llevaría a la acción correctiva equivocada. Comparte `consolidarPorLab()` con la tabla resumen para que ambos partan del mismo conteo.
- **Banner de documento preliminar** — mientras el cálculo siga en revisión, el informe se publica marcado como preliminar y no oficial (`.banner-preliminar` arriba de las pestañas de área, más la etiqueta "Preliminar" en la tarjeta de `publicaciones/informes.html`). Se retira solo cuando la ronda se declara definitiva.

**Pipeline anterior (Excel, hasta EA-001-2025)** — `extract_excel_to_csv.py`, `anonymize_data.py`, `calculate_zscore.py` (con `CODIGO_ENSAYO` fijo). Se conservan por referencia histórica; no aplican a rondas nuevas. Nota: el ALP de EA-001-2025 se publicó con CV 68.7%, compatible con esta misma bimodalidad sin detectar.

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

#### Monitorear qué laboratorios han reportado (ronda activa)

`scripts/reporte_participacion.py` — herramienta de seguimiento. Lee la ronda activa de `data/config.json`, consulta la colección `resultados_generales` filtrando por ese `codigo_ensayo`, y lista los laboratorios que han reportado con la cantidad de analitos (desglose Química / Uroanálisis + total) y la fecha de reporte, ordenados por nombre.

```bash
conda activate concalab
python scripts/reporte_participacion.py
```

Salida:
- **Tabla en consola** (Laboratorio · Fecha · Química · Uroanálisis · Total).
- **`support/participacion_<codigo>.html`** — versión imprimible/compartible con los colores del proyecto.

**Sin código anónimo a propósito:** esta tabla se difunde a los participantes por correo, por lo que **nunca** debe incluir `cod_anonimo` (asociar nombre ↔ código de-anonimizaría los informes públicos). Aun así lleva nombres reales, por eso `support/participacion_*.html` está en `.gitignore` y **no se commitea ni se publica en el sitio**. El script en sí (solo lógica, sin datos) sí es seguro de versionar.

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
