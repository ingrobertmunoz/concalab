# Contexto para Agentes de AI — CONCALAB-UASD

## � ¿Qué es CONCALAB-UASD?

**CONCALAB-UASD** (Control de Calidad de Laboratorios) es un organismo adscrito a la **Universidad Autónoma de Santo Domingo (UASD)**, República Dominicana. Su misión es garantizar la calidad analítica de los laboratorios clínicos del país mediante **programas de evaluación externa de calidad (EEC)**, también conocidos como **ensayos de aptitud (Proficiency Testing)**.

En la práctica, CONCALAB:
- Envía muestras control a los laboratorios participantes.
- Recoge sus resultados analíticos.
- Calcula estadísticas de desempeño (**Z-Score**, media robusta, desviación estándar robusta, etc.).
- Emite informes que permiten a cada laboratorio conocer su nivel de concordancia respecto al grupo.

El marco normativo de referencia es la **ISO 13528:2022** (métodos estadísticos para ensayos de aptitud).

---

## 🎯 Finalidad del Sitio Web

Este repositorio contiene el **sitio web oficial** de CONCALAB-UASD, publicado en **[www.concalabuasd.com](https://www.concalabuasd.com)**. Cumple tres funciones principales:

| Función | Descripción |
|---|---|
| **Plataforma informativa** | Presenta la misión, visión, historia, marco legal y servicios de la institución. |
| **Portal educativo** | Ofrece recursos de capacitación continua en control de calidad para profesionales de laboratorio. |
| **Centro de transparencia** | Publica resultados de ensayos de aptitud con visualizaciones interactivas (histogramas, gráficos de Z-Score) que permiten a los laboratorios evaluar su desempeño. |

---

## 🏗 Arquitectura Técnica

### Stack tecnológico

- **Tipo:** Sitio web estático (Static Site), sin framework de build.
- **Lenguajes:** HTML5, CSS3, JavaScript (Vanilla ES6+).
- **Gráficos:** [Plotly.js](https://plotly.com/javascript/) para las visualizaciones de datos de ensayos de aptitud.
- **Backend ligero:** [Firebase](https://firebase.google.com/) — Firestore para el formulario de ingreso de resultados de laboratorios y Analytics.
- **Hosting primario:** GitHub Pages (rama `master`, carpeta raíz).
- **Hosting alternativo:** Firebase Hosting (proyecto `concalab-uasd-64ff4`).
- **Dominio:** `www.concalabuasd.com` (definido en `CNAME`).
- **Repositorio:** `ingrobertmunoz/concalab`.

### Cómo se sirve

No requiere `npm install` ni proceso de build. Se abre directamente en el navegador (`index.html`) o se despliega vía `git push origin master` a GitHub Pages.

---

## 📂 Estructura del Proyecto

```
CONCALAB/
├── index.html                     # Página principal (hero, servicios, CTA)
├── contacto.html                  # Formulario de contacto
├── servicios.html                 # Servicios de CONCALAB
├── miembros.html                  # Directorio de laboratorios participantes
├── portal-educativo.html          # Recursos educativos (acordeones)
├── resultados.html                # Página de resultados / ingreso de datos
│
├── publicaciones/
│   ├── informes.html              # Listado de informes publicados
│   ├── informes/
│   │   └── EA-001-2025.html       # Informe interactivo de ensayo de aptitud
│   └── protocolos.html            # Protocolos de ensayos
│
├── sobre-nosotros/
│   ├── quienes-somos.html         # Misión, visión y valores
│   ├── historia.html              # Historia institucional
│   └── marco-legal.html           # Marco legal y certificaciones
│
├── css/
│   ├── main.css                   # Estilos principales + variables CSS (design tokens)
│   ├── responsive.css             # Media queries
│   └── animations.css             # Animaciones y efectos de scroll
│
├── js/
│   ├── main.js                    # Lógica general (nav, dropdowns, menú hamburguesa)
│   ├── search.js                  # Buscador global (indexa contenido de la página)
│   ├── scroll-reveal.js           # Animaciones al hacer scroll
│   ├── charts.js                  # Renderizado de gráficos Plotly
│   ├── results-form.js            # Formulario de ingreso de resultados (Firebase)
│   └── firebase-config.js         # Config e inicialización de Firebase
│
├── data/
│   ├── ensayos_aptitud.json       # Datos de ensayos en formato JSON
│   ├── ensayos_aptitud_consolidado.csv  # Datos consolidados en CSV
│   ├── ensayos_con_zscore.csv     # Datos con Z-Scores calculados
│   ├── laboratorios.json          # Catálogo de laboratorios participantes
│   ├── reporte_estadistico.txt    # Reporte estadístico en texto plano
│   ├── reporte_histogramas.html   # Histogramas pre-renderizados (Plotly)
│   └── informes/
│       └── EA-001-2025.json       # Datos JSON para el informe interactivo
│
├── scripts/                       # Utilidades Python (NO se publican al sitio)
│   ├── extract_excel_to_csv.py    # Extrae datos de Excel a CSV
│   ├── anonymize_data.py          # Anonimiza datos de laboratorios
│   ├── calculate_zscore.py        # Calcula Z-Scores (ISO 13528 / Algoritmo A)
│   ├── generate_report.py         # Genera informes HTML con gráficos
│   ├── parse_labs.py              # Parsea información de laboratorios
│   └── update_members_html.py     # Actualiza miembros.html desde datos
│
├── support/                       # Documentación de soporte (NO se publica)
│   ├── analitos.md                # Clasificación de analitos evaluados
│   ├── guia_metrologica.md        # Guía metrológica
│   ├── Labs info.md               # Listado de laboratorios
│   └── ISO-13528-2022.pdf         # Norma ISO de referencia
│
├── assets/
│   └── images/                    # Imágenes del sitio (logo, hero, etc.)
│
├── pic/                           # Imágenes adicionales
│
├── CNAME                          # Dominio para GitHub Pages
├── firebase.json                  # Configuración de Firebase Hosting
├── .firebaserc                    # Proyecto Firebase: concalab-uasd-64ff4
├── .gitignore                     # Excluye node_modules, .env, archivos sensibles
├── README.md                      # Documentación del proyecto
└── Agents.md                      # ← Este archivo
```

---

## 🎨 Sistema de Diseño

### Colores institucionales (variables CSS en `css/main.css`)

| Variable              | Valor      | Uso                        |
|-----------------------|------------|----------------------------|
| `--primary-color`     | `#003f87`  | Azul UASD — headers, nav, links |
| `--secondary-color`   | `#fdb913`  | Dorado UASD — CTAs, acentos  |
| `--accent-color`      | `#0056b3`  | Azul intermedio              |
| `--text-dark`         | `#333333`  | Texto principal              |
| `--text-light`        | `#666666`  | Texto secundario             |
| `--bg-light`          | `#f8f9fa`  | Fondo de secciones alternas  |
| `--bg-white`          | `#ffffff`  | Fondo principal              |
| `--success-color`     | `#28a745`  | Estados exitosos             |
| `--error-color`       | `#dc3545`  | Errores                      |
| `--border-color`      | `#e0e0e0`  | Bordes sutiles               |
| `--shadow`            | `0 2px 10px rgba(0,0,0,0.1)` | Sombra normal |
| `--shadow-hover`      | `0 5px 20px rgba(0,0,0,0.15)` | Sombra al hover |
| `--transition`        | `all 0.3s ease` | Transición estándar    |

### Tipografía

- **Fuente:** `'Segoe UI', Tahoma, Geneva, Verdana, sans-serif`
- **Tamaño base:** `16px`, `line-height: 1.6`

### Componentes reutilizables (clases CSS)

- **Layout:** `.container` (max-width: 1200px), `.grid`, `.grid-2`, `.grid-3`, `.grid-4`
- **Cards:** `.card`, `.card-icon`, `.card-title`, `.card-text`
- **Botones:** `.btn`, `.btn-primary` (dorado), `.btn-secondary` (outline blanco), `.btn-outline` (outline azul)
- **Formularios:** `.form-group`, `.form-label`, `.form-control`
- **Badges:** `.badge`, `.badge-primary`, `.badge-secondary`, `.badge-success`
- **Utilidades:** `.text-center`, `.mt-1`..`.mt-3`, `.mb-1`..`.mb-3`, `.d-none`, `.d-flex`, etc.

### Principios de diseño

- Estilo **limpio, académico e institucional**. No es un sitio de marketing agresivo.
- **Responsive:** Media queries en `responsive.css`; menú hamburguesa para móvil.
- **Animaciones:** Scroll reveal con observadores de intersección (`scroll-reveal.js`, `animations.css`).
- Mantener coherencia con la identidad visual de la UASD (azul y dorado).

---

## 📊 Pipeline de Datos (Ensayos de Aptitud)

El flujo de datos para los informes interactivos sigue estos pasos:

```
Excel original (datos crudos)
   │  scripts/extract_excel_to_csv.py
   ▼
CSV consolidado (data/ensayos_aptitud_consolidado.csv)
   │  scripts/anonymize_data.py
   ▼
CSV anonimizado
   │  scripts/calculate_zscore.py  (ISO 13528 Algoritmo A)
   ▼
CSV con Z-Scores (data/ensayos_con_zscore.csv)
   │  scripts/generate_report.py
   ▼
JSON del informe (data/informes/EA-001-2025.json)
   +
HTML interactivo (publicaciones/informes/EA-001-2025.html)
```

### Analitos evaluados

**Química Clínica** (26 analitos): Glucosa, Ácido Úrico, Colesterol, Colesterol HDL, Triglicéridos, Urea, Creatinina, Proteínas Total, Albúmina, Bilirrubina Total, Bilirrubina Directa, Amilasa, Lipasa, ALP, AST, ALT, Gamma GGT, LDH, CK-Total, Calcio, Fósforo, Cloruro, Sodio, Potasio, Magnesio, Hierro.

**Uroanálisis** (10 analitos): Bilirrubina, Sangre, Glucosa, Cetonas, Leucocitos, Nitritos, pH, Proteínas T., Densidad, Urobilinógeno.

### Estadísticas calculadas por analito

- **Media robusta** y **Desviación estándar robusta** (Algoritmo A, ISO 13528)
- **Z-Score** por laboratorio: `Z = (resultado - media_robusta) / desv_robusta`
- **Clasificación de desempeño**: |Z| ≤ 2 → Satisfactorio, 2 < |Z| < 3 → Cuestionable, |Z| ≥ 3 → Insatisfactorio

---

## 🔥 Integración con Firebase

- **Firestore:** Se usa para almacenar los resultados que los laboratorios ingresan a través del formulario en `resultados.html` (lógica en `js/results-form.js`).
- **Auth:** Autenticación por email/contraseña para restringir el ingreso de resultados a laboratorios registrados.
- **Analytics:** Google Analytics integrado vía Firebase.
- **Hosting:** Configuración alternativa disponible en `firebase.json`.

---

## 📁 Archivos Sensibles (NO publicar)

Los siguientes archivos contienen información confidencial y están excluidos del despliegue:

- `support/codigos_laboratorios_secretos.md` — Códigos secretos de identificación de laboratorios (en `.gitignore` y excluido en `firebase.json`).
- `scripts/` — Scripts Python de procesamiento (excluidos en `firebase.json`).
- `.env` — Variables de entorno (en `.gitignore`).

---

## � Despliegue

### GitHub Pages (principal)

```bash
git add .
git commit -m "Descripción del cambio"
git push origin master
```
GitHub Pages actualiza automáticamente desde la rama `master`, carpeta raíz.

### Firebase Hosting (alternativo)

```bash
firebase deploy --only hosting
```

### Verificación local

No se requiere servidor. Basta con abrir `index.html` directamente en el navegador. Para funcionalidades de Firebase (formularios), se puede usar `firebase serve`.

---

## 🧭 Navegación del Sitio

```
Inicio (index.html)
├── Publicaciones
│   ├── Protocolos (publicaciones/protocolos.html)
│   └── Informes (publicaciones/informes.html)
│       └── EA-001-2025 (publicaciones/informes/EA-001-2025.html)
├── Portal Educativo (portal-educativo.html)
├── Servicios (servicios.html)
├── Miembros (miembros.html)
├── Sobre Nosotros
│   ├── Quiénes Somos (sobre-nosotros/quienes-somos.html)
│   ├── Historia (sobre-nosotros/historia.html)
│   └── Marco Legal (sobre-nosotros/marco-legal.html)
├── Resultados (resultados.html)
└── Contacto (contacto.html)
```

---

## ⚙️ Convenciones para Contribuir

1. **Idioma del contenido:** Español (República Dominicana).
2. **No usar frameworks JS/CSS** — Todo es vanilla. No introducir React, Vue, Tailwind, etc.
3. **Usar las variables CSS** definidas en `css/main.css` para colores, sombras y transiciones.
4. **Mantener el diseño institucional** — Limpio, profesional, coherente con la identidad UASD.
5. **Datos de laboratorios:** Siempre anonimizados en el sitio público. Los nombres reales nunca deben aparecer en archivos publicados.
6. **Scripts Python** son herramientas de soporte local, no forman parte del sitio desplegado.
7. **Nombres de archivos HTML** en minúsculas con guiones (`portal-educativo.html`, no `PortalEducativo.html`).
8. **Informes de ensayos** siguen la nomenclatura `EA-XXX-YYYY` (Ensayo de Aptitud - número - año).

---

## 🗺 Roadmap Actual

1. **Dashboard interactivo completo** — Expandir las visualizaciones de ensayos de aptitud para cubrir todos los analitos con gráficos de Z-Score, histogramas y estadísticas comparativas.
2. **Automatización del pipeline** — Simplificar el flujo de Excel → CSV → Z-Score → Informe para que los coordinadores puedan generar informes sin intervención técnica.
3. **Mejora del portal educativo** — Agregar más contenido formativo sobre control de calidad, normativas ISO y buenas prácticas de laboratorio.
4. **Formulario de resultados** — Completar la integración con Firebase para que los laboratorios ingresen sus resultados directamente en el sitio.
