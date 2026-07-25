/*
 * Lógica del informe de ensayo de aptitud — compartida por todas las rondas.
 *
 * Vivía embebida en la página de cada ronda, que se creaba clonando la
 * anterior. Eso hacía que cada corrección hubiera que repetirla en cada copia y
 * que las rondas divergieran en silencio: la de 2025 ordenaba mal los
 * identificadores, no acotaba los ejes y no tenía métrica global, defectos ya
 * resueltos en la de 2026.
 *
 * La página por ronda solo declara `window.INFORME` y un punto de montaje.
 * Todo lo demás —esqueleto, gráficas, tablas— se construye aquí.
 *
 * REGLA: este archivo no calcula métricas. Los números vienen ya calculados
 * por scripts/calcular_zscore.py y verificados por scripts/validar_informe.py.
 * Aquí solo se decide cómo mostrarlos: orden de la tabla, recorte de ejes,
 * qué barras se rotulan, colores. Si hace falta una cifra nueva, se agrega al
 * JSON, no aquí. Ver CLAUDE.md → "Todas las métricas se calculan en Python".
 *
 * Requiere Plotly y css/informe.css.
 */

const CFG = Object.assign({
    codigo: '',
    area: 'quimica',
    json: '',
    preliminar: false,
    areas: [],
    montaje: 'informe-root',
}, window.INFORME || {});

// Nombres de las clasificaciones A/C/I según el modelo. En el modelo CLIA
// (aptitud al uso) se usan los términos de PROASECAL/ESfEQA; en el de consenso,
// la nomenclatura del z-score de ISO 13528. El consenso queda EXACTAMENTE igual.
const _clia = CFG.modelo === 'clia';
const LB = {
    Ap:     _clia ? 'Satisfactorios'    : 'Aceptables',
    Cp:     _clia ? 'Alertas'           : 'Cuestionables',
    Ip:     _clia ? 'No satisfactorios' : 'Inaceptables',
    A:      _clia ? 'Satisfactorio'     : 'Aceptable',
    C:      _clia ? 'Alerta'            : 'Cuestionable',
    I:      _clia ? 'No satisfactorio'  : 'Inaceptable',
    conf:   _clia ? 'Satisfactorios'    : 'Conformes',
    noconf: _clia ? 'No satisfactorios' : 'No conformes',
};

// ── Esqueleto del informe ────────────────────────────────────────────────
// Se genera aquí para que una ronda nueva no tenga que clonar 130 líneas de
// markup cuyos IDs deben coincidir exactamente con los que busca este archivo.
function bannerPreliminar() {
    if (!CFG.preliminar) return '';
    return `
    <div class="banner-preliminar">
        <div class="titulo">
            <span class="etiqueta">Preliminar</span>
            Documento en proceso de cálculo — no oficial
        </div>
        <p>
            Este informe se publica de forma <strong>preliminar</strong> mientras el
            tratamiento estadístico de la ronda continúa en revisión. Las cifras, los
            valores asignados y las clasificaciones que aquí aparecen
            <strong>pueden cambiar</strong> y no constituyen el resultado oficial de la
            ronda ${CFG.codigo}. CONCALAB-UASD emitirá el informe definitivo y notificará
            su publicación a los laboratorios participantes.
        </p>
    </div>`;
}

// Las pestañas se declaran por ronda: cuáles áreas existen y cuáles ya tienen
// informe. Un área sin JSON se muestra deshabilitada, no se oculta, para que
// el participante sepa que está en camino.
function pestanasArea() {
    if (!CFG.areas || CFG.areas.length < 2) return '';
    return `
    <div class="area-tabs" role="tablist">
        ${CFG.areas.map(a => a.disponible
            ? `<button class="area-tab${a.clave === CFG.area ? ' active' : ''}" role="tab"
                       aria-selected="${a.clave === CFG.area}"
                       ${a.url ? `onclick="location.href='${a.url}'"` : ''}>${a.nombre}</button>`
            : `<button class="area-tab" role="tab" aria-selected="false" disabled
                       title="El informe de ${a.nombre} se publicará por separado">
                   ${a.nombre}<span class="pendiente">${a.estado || 'En procesamiento'}</span>
               </button>`).join('\n        ')}
    </div>`;
}

const ESQUELETO = `<!-- Aviso global de analitos no concluyentes -->
<div id="global-alert"></div>

<!-- Report Header -->
<div class="report-header card reveal" id="report-header">
    <div class="loading" id="loading-msg">
        <div class="spinner"></div>
        <p style="margin-top: 1rem;">Cargando datos del informe...</p>
    </div>
</div>

<!-- Summary Cards -->
<div class="summary-cards" id="summary-cards" style="display:none;"></div>

<!-- Desempeño global: métrica por laboratorio, no por resultado -->
<div class="summary-table-container" id="global-metric" style="display:none;">
    <h3>Desempeño Global de los Laboratorios</h3>
    <p class="tabla-nota" id="global-metric-note"></p>
    <div class="metrica-global">
        <div class="metrica-titular">
            <div class="cifra" id="mg-cifra">—</div>
            <div class="detalle" id="mg-detalle"></div>
        </div>
        <div class="metrica-estratos" id="mg-estratos"></div>
    </div>
    <p class="tabla-nota" id="global-metric-concentracion"></p>
</div>

<!-- Criterios de aceptación (se rellena cuando el JSON los trae, p. ej. modelo CLIA) -->
<div class="methodology" id="criteria-panel" style="display:none;"></div>


<!-- Navigation Index -->
<div class="nav-toc" id="nav-toc" style="display:none;">
    <h3>Índice de Analitos</h3>
    <ul class="pills" id="nav-pills"></ul>
</div>

<!-- All Analytes Charts (rendered dynamically) -->
<div id="all-analytes"></div>

<!-- Heatmap -->
<div class="heatmap-section" id="heatmap-section" style="display:none;">
    <h3>Mapa de Desempeño General</h3>
    <p>Laboratorio vs. Analito — Color según Z-Score. Las celdas grises indican que el laboratorio no
        participó en ese analito.</p>
    <div id="heatmap-chart"></div>
</div>

<!-- Resumen por laboratorio -->
<div class="summary-table-container" id="lab-table-container" style="display:none;">
    <h3>Resumen por Laboratorio</h3>
    <p class="tabla-nota" id="lab-table-note"></p>
    <table class="summary-table tabla-labs">
        <thead>
            <tr>
                <th data-sort="id" class="sortable">Laboratorio</th>
                <th data-sort="n" class="sortable num">Analitos evaluados</th>
                <th data-sort="a" class="sortable num">${LB.conf}</th>
                <th data-sort="c" class="sortable num">${LB.Cp}</th>
                <th data-sort="i" class="sortable num">${LB.noconf}</th>
                <th data-sort="pct" class="sortable">% Conformidad</th>
            </tr>
        </thead>
        <tbody id="lab-tbody"></tbody>
    </table>
</div>

<!-- Summary Table -->
<div class="summary-table-container" id="summary-table-container" style="display:none;">
    <h3>📊 Resumen Estadístico por Analito</h3>
    <table class="summary-table">
        <thead>
            <tr>
                <th>Analito</th>
                <th>n</th>
                <th>X* (Valor Asignado)</th>
                <th>σ* (SD Robusta)</th>
                <th>CV (%)</th>
                <th>✅ A</th>
                <th>⚠️ C</th>
                <th>❌ I</th>
            </tr>
        </thead>
        <tbody id="summary-tbody"></tbody>
    </table>
</div>

<!-- CV Alerts -->
<div id="cv-alerts"></div>

<!-- Methodology -->
<div class="methodology" id="methodology-box" style="display:none;">
    <strong>Metodología:</strong><br>
    • <strong>Valor asignado (X*):</strong> Media robusta — Algoritmo A, ISO 13528:2022<br>
    • <strong>Desviación estándar (σ*):</strong> SD robusta — Algoritmo S, ISO 13528:2022<br>
    • <strong>Z-Score:</strong> z = (x − X*) / σ*, donde x es el resultado del laboratorio<br>
    • <strong>Criterios:</strong> |z| ≤ 2 → Aceptable &nbsp;|&nbsp; 2 &lt; |z| &lt; 3 → Cuestionable
    &nbsp;|&nbsp; |z| ≥ 3 → Inaceptable<br>
    • <strong>CV umbral:</strong> Se alerta cuando CV &gt; 15% (alto) o CV &gt; 30% (muy alto)
</div>

`;

function montarEsqueleto() {
    const raiz = document.getElementById(CFG.montaje);
    if (!raiz) {
        console.error(`informe.js: no existe el punto de montaje #${CFG.montaje}`);
        return false;
    }
    raiz.innerHTML = bannerPreliminar() + pestanasArea() + ESQUELETO;
    return true;
}

// ================================================================
// INFORME INTERACTIVO — EA-001-2026
// Lee JSON y dibuja TODOS los analitos con Plotly.js
// ================================================================

const JSON_URL = CFG.json;

function zColor(z) {
    const abs = Math.abs(z);
    if (abs <= 2) return '#28a745';
    if (abs < 3) return '#ffc107';
    return '#dc3545';
}

function safeId(name) {
    return name.replace(/\s/g, '-').replace(/[().]/g, '');
}

// Etiqueta legible del Error Total Permitido (modelo CLIA): la regla declarada
// y, entre paréntesis, el δE ya resuelto en la unidad del analito. Marca los
// analitos que CLIA no regula (Lipasa, Bilirrubina Directa → variación biológica).
function etaLabel(eta, unidad) {
    if (!eta) return '';
    const partes = [];
    if (eta.pct != null) partes.push(`±${eta.pct}%`);
    if (eta.abs != null) partes.push(`±${eta.abs} ${eta.unidad || unidad}`);
    const regla = partes.join(eta.regla === 'mayor' ? ' o ' : ' ');
    const soloAbs = eta.pct == null && eta.abs != null;
    const resuelto = (!soloAbs && eta.delta_e != null)
        ? ` (±${Number(eta.delta_e).toFixed(2)} ${unidad})` : '';
    const vb = (eta.fuente && eta.fuente.includes('EFLM')) ? ' <em>(EFLM, no CLIA)</em>' : '';
    return regla + resuelto + vb;
}

// ── Evaluación por grupo de pares ─────────────────────────────────────
// Cuando dos plataformas analíticas no son comparables entre sí, cada una
// recibe su propio valor asignado (ISO 13528 §7). Un grupo demasiado
// pequeño no da estadística defendible: esos laboratorios se reportan sin
// evaluar en vez de anexarlos al grupo más parecido, que sería incorrecto.
function esPorPares(a) {
    return a.evaluacion === 'grupo_pares';
}

// Paleta por grupo. Es identidad, no estado: nunca los colores A/C/I.
const COLOR_GRUPO = ['#1f4e9c', '#c77f0a', '#00857a', '#7b4ea3'];

function colorGrupo(a, nombre) {
    const evs = a.grupos.filter(g => g.evaluado).map(g => g.nombre);
    return COLOR_GRUPO[evs.indexOf(nombre) % COLOR_GRUPO.length];
}

function paresAlert(a) {
    const ev = a.grupos.filter(g => g.evaluado);
    const sin = a.grupos.filter(g => !g.evaluado);
    const filas = ev.map(g => `
        <li><span class="punto-grupo" style="background:${colorGrupo(a, g.nombre)}"></span>
        <strong>${g.nombre}</strong> — ${g.n} laboratorios ·
        X* = ${g.valor_asignado} ${a.unidad} · σ* = ${g.sd_robusta} · CV ${g.cv}%
        ${g.n_suficiente === false ? ' <em>(n &lt; 12, ver nota)</em>' : ''}</li>`).join('');

    const nSmall = ev.filter(g => g.n_suficiente === false);
    return `<div class="alert-box alert-pares" style="margin-bottom:1rem;">
        <strong>Evaluación por grupo de pares (ISO 13528).</strong><br>
        Las plataformas analíticas de este analito no son comparables entre sí, por lo que
        un único valor asignado no describiría correctamente a ninguna. Cada grupo se evalúa
        contra su propio consenso, y el Z-Score de cada laboratorio se calcula dentro del
        grupo que le corresponde:
        <ul style="margin:.5rem 0 .5rem 1.2rem;">${filas}</ul>
        ${sin.length ? `<div class="nota-pares"><strong>Sin evaluar:</strong> ` +
            sin.map(g => `${g.nombre} (${g.n} laboratorio${g.n > 1 ? 's' : ''})`).join(', ') +
            `. Un grupo de pares con menos de 8 participantes no permite una estadística
             robusta defendible. Esos resultados se publican como referencia, sin Z-Score:
             asignarlos a otro grupo los evaluaría contra un método que no es el suyo.</div>` : ''}
        ${nSmall.length ? `<div class="nota-pares">Los grupos con menos de 12 participantes
             quedan por debajo del n recomendado por ISO 13528 para estadística robusta;
             sus Z-Score deben interpretarse con esa reserva.</div>` : ''}
    </div>`;
}

// ── Analitos con evaluación agrupada no confiable ─────────────────────
// Cuando en un analito conviven dos plataformas analíticas cuyas medianas
// difieren >= 1.5x, el Algoritmo A no converge a un centro único: infla la
// σ* robusta y la ventana de aceptación se ensancha hasta absorber casi
// todos los resultados. La clasificación resultante parece excelente pero
// no mide desempeño. El JSON marca esos analitos con evaluacion_confiable
// = false; aquí se advierte en vez de presentarlos como buen resultado.
function bimodalAlert(a) {
    const g = (a.aviso_bimodal?.grupos || [])
        .map(x => `<li><strong>${x.plataforma}</strong> — ${x.n} laboratorios, mediana ${x.mediana} ${a.unidad}</li>`)
        .join('');
    return `<div class="alert-box alert-bimodal" style="margin-bottom:1rem;">
        <strong>Evaluación no concluyente — resultados de referencia únicamente.</strong><br>
        En este analito conviven plataformas analíticas cuyos resultados difieren por un factor de
        <strong>${a.aviso_bimodal?.razon}x</strong>, por lo que no son directamente comparables entre sí:
        <ul style="margin:.5rem 0 .5rem 1.2rem;">${g}</ul>
        Un único valor asignado para ambos grupos produce una σ* artificialmente amplia
        (σ* = ${a.sd_robusta} sobre X* = ${a.valor_asignado} ${a.unidad}, CV ${a.cv}%). En consecuencia,
        <strong>los Z-Score de este analito no deben interpretarse como desempeño</strong>: la mayoría
        resultaría aceptable por lo ancho del criterio, no por la calidad del resultado.
        CONCALAB-UASD evaluará este analito por grupo de pares conforme a ISO 13528.
    </div>`;
}

// El esqueleto se monta de forma síncrona antes de pedir el JSON: renderReport
// busca elementos por id y el fetch resuelve después, pero dejarlo al azar del
// orden de ejecución sería frágil.
if (montarEsqueleto()) {
    fetch(JSON_URL)
        .then(res => {
            if (!res.ok) throw new Error('No se pudo cargar el JSON');
            return res.json();
        })
        .then(data => renderReport(data))
        .catch(err => {
            document.getElementById('loading-msg').innerHTML =
                `<p style="color: #dc3545;">❌ Error cargando datos: ${err.message}</p>`;
        });
}

function renderReport(data) {
    // Header
    const header = document.getElementById('report-header');
    header.innerHTML = `
    <span class="badge">${data.codigo}</span>
    <h2>Informe de Ensayo de Aptitud</h2>
    <p>${data.metodologia} — Fecha: ${data.fecha}</p>
`;

    // Criterios de aceptación al inicio. Solo aparece si el JSON los declara
    // (modelo CLIA); un número nuevo se agrega en Python, no aquí.
    const critPanel = document.getElementById('criteria-panel');
    const crit = data.criterios_aceptacion;
    if (crit && critPanel) {
        critPanel.style.display = 'block';
        critPanel.innerHTML = `
        ${crit.que_es_clia ? `<p style="margin:0 0 .8rem 0;"><strong>¿Qué es CLIA?</strong> ${crit.que_es_clia}</p>` : ''}
        <strong>Criterios de aceptación</strong><br>
        • <strong>Valor asignado (X*):</strong> ${crit.valor_asignado}<br>
        • <strong>Dispersión (σ*, CV):</strong> ${crit.dispersion}<br>
        • <strong>Evaluación:</strong> ${crit.evaluacion}<br>
        • <strong>Niveles:</strong> ${crit.niveles
            .map(n => `<strong>${n.nombre}</strong> ${n.regla}`).join(' &nbsp;|&nbsp; ')}<br>
        • <strong>ETa:</strong> ${crit.eta_fuente}`;
    }

    // Summary cards
    const r = data.resumen;
    const pctA = (r.aceptables / r.total * 100).toFixed(1);
    const pctC = (r.cuestionables / r.total * 100).toFixed(1);
    const pctI = (r.inaceptables / r.total * 100).toFixed(1);

    // Los JSON anteriores no traen el conteo de laboratorios; se deriva de
    // los propios datos para que la portada funcione con cualquier informe.
    const nLabs = data.resumen.laboratorios
        ?? new Set(data.analitos.flatMap(a => a.laboratorios.map(l => l.id))).size;

    const cards = document.getElementById('summary-cards');
    cards.style.display = 'grid';
    cards.innerHTML = `
    <div class="summary-card" style="background: #4a5568;">
        <div class="number">${nLabs}</div>
        <div class="label">Laboratorios Participantes</div>
    </div>
    <div class="summary-card" style="background: #28a745;">
        <div class="number">${r.aceptables}</div>
        <div class="label">${LB.Ap} (${pctA}%)</div>
    </div>
    <div class="summary-card" style="background: #ffc107; color: #333;">
        <div class="number">${r.cuestionables}</div>
        <div class="label">${LB.Cp} (${pctC}%)</div>
    </div>
    <div class="summary-card" style="background: #dc3545;">
        <div class="number">${r.inaceptables}</div>
        <div class="label">${LB.Ip} (${pctI}%)</div>
    </div>
    <div class="summary-card" style="background: var(--primary-color);">
        <div class="number">${r.total}</div>
        <div class="label">Total Evaluaciones</div>
    </div>
    <div class="summary-card" style="background: #6f42c1;">
        <div class="number">${data.analitos.length}</div>
        <div class="label">Analitos Evaluados</div>
    </div>
`;

    // Aviso global: analitos cuya evaluación agrupada no es concluyente.
    const noConcl = data.analitos.filter(a => a.evaluacion_confiable === false);
    if (noConcl.length) {
        document.getElementById('global-alert').innerHTML = `
        <div class="alert-box alert-bimodal">
            <strong>${noConcl.length} analito(s) con evaluación no concluyente:
            ${noConcl.map(a => a.nombre).join(', ')}.</strong><br>
            Se presentan con fines de referencia y quedan pendientes de evaluación por grupo de pares.
            Sus clasificaciones no deben leerse como desempeño, y por lo tanto tampoco están
            reflejadas de forma representativa en los totales de esta portada.
        </div>`;
    }

    // Navigation pills
    const navToc = document.getElementById('nav-toc');
    navToc.style.display = 'block';
    const pills = document.getElementById('nav-pills');
    data.analitos.forEach(a => {
        pills.innerHTML += `<li><a href="#${safeId(a.nombre)}">${a.nombre}</a></li>`;
    });
    pills.innerHTML += `<li><a href="#heatmap-section" class="pill-summary">🗺️ Heatmap</a></li>`;
    pills.innerHTML += `<li><a href="#lab-table-container" class="pill-summary">🏥 Por Laboratorio</a></li>`;
    pills.innerHTML += `<li><a href="#resumen-tabla" class="pill-summary">📊 Resumen</a></li>`;

    // Render ALL analytes
    const container = document.getElementById('all-analytes');
    data.analitos.forEach((a, i) => {
        const id = safeId(a.nombre);
        // Calculados en calcular_zscore.py y verificados por
        // validar_informe.py; aquí solo se leen.
        const { A: countA, C: countC, I: countI, NE: countNE } = a.conteos;

        // Un analito bimodal ya tiene explicada su dispersión: mostrar la
        // alerta de CV encima sería redundante y desviaría la lectura.
        const cvAlert = esPorPares(a)
            ? paresAlert(a)
            : a.evaluacion_confiable === false
                ? bimodalAlert(a)
                : a.cv > 30
                    ? `<div class="alert-box alert-danger" style="margin-bottom:1rem;">🔴 <strong>CV = ${a.cv}% (Muy Alto).</strong> Se recomienda revisar los métodos analíticos de los laboratorios participantes. La alta dispersión de resultados sugiere diferencias significativas en metodología, calibración o condiciones preanalíticas.</div>`
                    : a.cv > 15
                        ? `<div class="alert-box alert-warning" style="margin-bottom:1rem;">⚠️ <strong>CV = ${a.cv}% (Alto).</strong> Se recomienda revisar los métodos analíticos de los laboratorios participantes. La dispersión elevada puede indicar diferencias en metodología o calibración entre laboratorios.</div>`
                        : '';

        // En un analito por grupo de pares no existe un X* único: cada
        // plataforma tiene el suyo, así que se muestra una fila por grupo.
        const stats = esPorPares(a)
            ? `<div class="stat"><strong>n:</strong> ${a.n} labs</div>
               ${a.grupos.filter(g => g.evaluado).map(g => `
               <div class="stat stat-grupo">
                   <strong>${g.nombre}</strong><br>
                   n = ${g.n} · X* = ${g.valor_asignado} ${a.unidad} · σ* = ${g.sd_robusta} · CV ${g.cv}%${g.eta ? ` · ETa ${etaLabel(g.eta, a.unidad)}` : ''}
               </div>`).join('')}
               <div class="stat">✅ ${countA} ⚠️ ${countC} ❌ ${countI}${countNE ? ` · ${countNE} sin evaluar` : ''}</div>`
            : `<div class="stat"><strong>n:</strong> ${a.n} labs</div>
               <div class="stat"><strong>X*:</strong> ${a.valor_asignado} ${a.unidad}</div>
               <div class="stat"><strong>σ*:</strong> ${a.sd_robusta} ${a.unidad}</div>
               <div class="stat"><strong>CV:</strong> ${a.cv}%</div>
               ${a.eta ? `<div class="stat"><strong>ETa:</strong> ${etaLabel(a.eta, a.unidad)}</div>` : ''}
               <div class="stat">✅ ${countA} ⚠️ ${countC} ❌ ${countI}</div>`;

        container.innerHTML += `
        <div class="analyte-section" id="${id}">
            <h2>🧪 ${a.nombre}${esPorPares(a) ? ' <span class="tag-pares">grupo de pares</span>' : ''}</h2>
            <div class="analyte-stats" style="display:flex;">${stats}</div>
            ${cvAlert}
            <div id="hist-${i}" style="width:100%; min-height:${esPorPares(a) ? 430 : 380}px;"></div>
            <div id="bar-${i}" style="width:100%; margin-top:1rem; min-height:450px;"></div>
        </div>
    `;
    });

    dibujarCuandoSeVean(data);

    // Summary table + alerts
    renderGlobalMetric(data);
    renderLabTable(data);
    renderSummaryTable(data.analitos);
    renderCVAlerts(data.analitos);
    // El recuadro de metodología del pie describe el z-score de consenso
    // (z=(x−X*)/σ*). En el modelo CLIA eso sería incorrecto: el panel de
    // criterios del inicio ya declara la metodología correcta, así que se oculta.
    document.getElementById('methodology-box').style.display =
        data.criterios_aceptacion ? 'none' : 'block';
}

function renderCharts(analyte, index) {
    const resultados = analyte.laboratorios.map(l => l.resultado);
    const Z_VISTA = 5;

    // Centros de referencia del histograma: uno por grupo evaluado cuando
    // el analito va por grupo de pares, o el único X* cuando va agrupado.
    const centros = esPorPares(analyte)
        ? analyte.grupos.filter(g => g.evaluado).map(g => ({
            nombre: g.nombre, x: g.valor_asignado, s: g.sd_robusta,
            color: colorGrupo(analyte, g.nombre)
        }))
        : [{ nombre: null, x: analyte.valor_asignado, s: analyte.sd_robusta, color: '#dc3545' }];

    // El rango visible cubre todos los centros: con dos plataformas separadas
    // hay que ver ambas nubes, que es justamente lo que justifica separarlas.
    const xMin = Math.min(...centros.map(c => c.x - Z_VISTA * c.s));
    const xMax = Math.max(...centros.map(c => c.x + Z_VISTA * c.s));

    // Banda de aceptación: solo tiene sentido con un único criterio. Con grupos
    // de pares cada uno tendría el suyo y se solaparían, así que se omite y la
    // zona aceptable queda expresada en el gráfico de Z-Score.
    // En el modelo CLIA la banda es X* ± ETa (el límite regulatorio); en el de
    // consenso es X* ± 2σ*. El rango visible del eje sigue basado en σ* para no
    // ocultar la dispersión real de los laboratorios.
    const semiBanda = (CFG.modelo === 'clia' && analyte.eta)
        ? analyte.eta.delta_e
        : 2 * centros[0].s;
    const z2low = centros.length === 1 ? centros[0].x - semiBanda : null;
    const z2high = centros.length === 1 ? centros[0].x + semiBanda : null;

    const dentro = resultados.filter(v => v >= xMin && v <= xMax);
    const nBins = Math.max(8, Math.min(20, Math.floor(resultados.length / 2)));

    // Laboratorios cuyo resultado cae fuera del rango visible. No basta con
    // contarlos: cada laboratorio debe poder localizarse en su propio informe,
    // así que se dibujan como triángulos en el borde hacia el que se salen,
    // identificados al pasar el cursor.
    const fueraLabs = analyte.laboratorios
        .filter(l => l.resultado < xMin || l.resultado > xMax)
        .sort((a, b) => a.resultado - b.resultado);

    const marcadoresFuera = fueraLabs.length ? [{
        x: fueraLabs.map(l => l.resultado < xMin ? xMin : xMax),
        y: fueraLabs.map(() => 0),
        type: 'scatter',
        mode: 'markers',
        marker: {
            symbol: fueraLabs.map(l => l.resultado < xMin ? 'triangle-left' : 'triangle-right'),
            size: 15,
            color: '#dc3545',
            line: { color: 'white', width: 1.5 }
        },
        hovertext: fueraLabs.map(l =>
            `${l.id}<br>Resultado: ${l.resultado} ${analyte.unidad}<br>` +
            `${l.z_score === null ? 'Sin evaluar' : 'Z-Score: ' + l.z_score.toFixed(2)}` +
            `<br>Fuera del rango visible del gráfico`),
        hoverinfo: 'text',
        cliponaxis: false,
        showlegend: false
    }] : [];

    // Con grupo de pares se dibuja un histograma por grupo, superpuestos:
    // ver las dos nubes separadas es lo que hace evidente por qué no pueden
    // compartir un valor asignado.
    const bins = { start: xMin, end: xMax, size: (xMax - xMin) / nBins };
    const trazasHist = esPorPares(analyte)
        ? analyte.grupos.map(g => {
            const vals = analyte.laboratorios
                .filter(l => l.grupo === g.nombre).map(l => l.resultado);
            const color = g.evaluado ? colorGrupo(analyte, g.nombre) : '#9aa3b2';
            return {
                x: vals, type: 'histogram', name: `${g.nombre} (n=${g.n})`,
                xbins: bins,
                marker: { color, opacity: 0.72, line: { color, width: 1.2 } },
                hovertemplate: `${g.nombre}<br>Rango: %{x}<br>Frecuencia: %{y}<extra></extra>`
            };
        })
        : [{
            x: resultados, type: 'histogram', xbins: bins,
            marker: {
                color: 'rgba(26, 35, 126, 0.7)',
                line: { color: 'rgba(26, 35, 126, 1)', width: 1.5 }
            },
            hovertemplate: 'Rango: %{x}<br>Frecuencia: %{y}<extra></extra>',
            showlegend: false
        }];

    // Histogram
    Plotly.newPlot(`hist-${index}`, [...trazasHist, ...marcadoresFuera], {
        barmode: 'overlay',
        showlegend: esPorPares(analyte),
        legend: { orientation: 'h', y: -0.22, font: { size: 10 } },
        title: { text: `Distribución de Resultados — ${analyte.nombre} (${analyte.unidad})`, font: { size: 15, color: '#1a237e' } },
        xaxis: { title: `Resultado (${analyte.unidad})`, gridcolor: '#eee', range: [xMin, xMax] },
        // dtick fijo en 1 satura el eje cuando una barra concentra decenas
        // de laboratorios; solo se fuerza mientras las frecuencias son bajas.
        yaxis: {
            title: 'Frecuencia (n° de laboratorios)', gridcolor: '#eee',
            ...(dentro.length <= 12 ? { dtick: 1 } : {})
        },
        height: esPorPares(analyte) ? 430 : 380,
        margin: { l: 60, r: 30, t: 50, b: esPorPares(analyte) ? 90 : 50 },
        bargap: 0.05, plot_bgcolor: 'white', paper_bgcolor: 'white',
        shapes: [
            // Una línea de valor asignado por centro: con grupos de pares son
            // dos, y verlas separadas es el punto del gráfico.
            ...centros.map(c => ({
                type: 'line', x0: c.x, x1: c.x, y0: 0, y1: 1, yref: 'paper',
                line: { color: c.color, width: 2.5, dash: 'dash' }
            })),
            ...(z2low !== null ? [{
                type: 'rect', x0: z2low, x1: z2high, y0: 0, y1: 1, yref: 'paper',
                fillcolor: 'rgba(40, 167, 69, 0.1)', line: { width: 0 }
            }] : [])
        ],
        annotations: [
            ...centros.map((c, k) => ({
                x: c.x, y: 1 - k * 0.08, yref: 'paper', text: `X* = ${c.x}`,
                showarrow: false, font: { color: c.color, size: 11 },
                xanchor: 'left', xshift: 5
            })),
            // Se nombran los laboratorios, no solo su cantidad: quien busca su
            // propio código debe encontrarlo sin tener que abrir el tooltip.
            ...(fueraLabs.length ? [{
                x: 1, y: 1.02, xref: 'paper', yref: 'paper', xanchor: 'right',
                // Se listan hasta 3; más allá la línea desbordaría el ancho del
                // gráfico. El resto sigue accesible en sus marcadores del borde.
                text: '▶ Fuera del rango visible: ' + fueraLabs.slice(0, 3)
                    .map(l => `${l.id} = ${l.resultado} ${analyte.unidad}` +
                        (l.z_score === null ? ' (sin evaluar)' : ` (z ${l.z_score >= 0 ? '+' : ''}${l.z_score.toFixed(1)})`))
                    .join('  ·  ')
                    + (fueraLabs.length > 3 ? `  ·  y ${fueraLabs.length - 3} más (ver marcadores ◀ ▶)` : ''),
                showarrow: false, font: { color: '#c62828', size: 10 }
            }] : [])
        ]
    }, { responsive: true });

    // Z-Score bars. Los laboratorios sin grupo de pares suficiente no tienen
    // Z-Score: se excluyen de las barras y se declaran aparte, porque dibujarlos
    // en cero los haría parecer perfectos.
    const labs = analyte.laboratorios.filter(l => l.z_score !== null);
    const sinEvaluar = analyte.laboratorios.filter(l => l.z_score === null);
    const labLabels = labs.map(l => l.id);
    const zValues = labs.map(l => l.z_score);
    const colors = zValues.map(z => zColor(z));
    const hoverTexts = labs.map(l =>
        `${l.id}<br>Z-Score: ${l.z_score.toFixed(2)}<br>Resultado: ${l.resultado} ${analyte.unidad}` +
        (l.grupo ? `<br>Grupo: ${l.grupo}` : '')
    );

    // Eje acotado a |z| = 6. Un solo Z-Score extremo (se han visto de +56)
    // estira el eje y aplasta a todos los demás contra el cero, con lo que
    // desaparece la gradación que el gráfico debe mostrar. Las barras que lo
    // exceden se dibujan al tope pero conservan su valor real en la etiqueta
    // y en el tooltip, de modo que no se oculta información.
    const Z_VIS = 6;
    const zPlot = zValues.map(z => Math.max(-Z_VIS, Math.min(Z_VIS, z)));
    const recortadas = zValues.filter(z => Math.abs(z) > Z_VIS).length;
    // Etiqueta solo lo que exige atención: rotular las 37 barras satura el
    // gráfico y entierra justamente los valores que hay que leer.
    const etiquetas = zValues.map(z => Math.abs(z) > 2 ? z.toFixed(1) : '');

    Plotly.newPlot(`bar-${index}`, [{
        x: labLabels, y: zPlot, type: 'bar', orientation: 'v',
        marker: { color: colors, line: { color: 'rgba(0,0,0,0.15)', width: 0.5 } },
        text: etiquetas, textposition: 'outside', textfont: { size: 9 },
        cliponaxis: false,
        hovertext: hoverTexts, hoverinfo: 'text'
    }], {
        title: { text: `Z-Score por Laboratorio — ${analyte.nombre}`, font: { size: 15, color: '#1a237e' } },
        xaxis: { title: 'Laboratorio', tickangle: -45, tickfont: { size: 9 }, gridcolor: '#eee' },
        yaxis: { title: 'Z-Score', range: [-Z_VIS - 0.8, Z_VIS + 0.8], gridcolor: '#eee', zeroline: false },
        height: 450, margin: { l: 60, r: 60, t: 50, b: 100 },
        plot_bgcolor: 'white', paper_bgcolor: 'white',
        shapes: [
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 0, y1: 0, line: { color: '#666', width: 1 } },
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 2, y1: 2, line: { color: 'orange', width: 1.5, dash: 'dash' } },
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: -2, y1: -2, line: { color: 'orange', width: 1.5, dash: 'dash' } },
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 3, y1: 3, line: { color: 'red', width: 1.5, dash: 'dot' } },
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: -3, y1: -3, line: { color: 'red', width: 1.5, dash: 'dot' } },
            {
                type: 'rect', x0: 0, x1: 1, xref: 'paper', y0: -2, y1: 2,
                fillcolor: 'rgba(40, 167, 69, 0.05)', line: { width: 0 }
            }
        ],
        annotations: [
            { x: 1.02, xref: 'paper', y: 2, text: 'z=+2', showarrow: false, font: { color: 'orange', size: 9 } },
            { x: 1.02, xref: 'paper', y: -2, text: 'z=-2', showarrow: false, font: { color: 'orange', size: 9 } },
            { x: 1.02, xref: 'paper', y: 3, text: 'z=+3', showarrow: false, font: { color: 'red', size: 9 } },
            { x: 1.02, xref: 'paper', y: -3, text: 'z=-3', showarrow: false, font: { color: 'red', size: 9 } },
            ...((() => {
                // Ambas notas comparten la línea superior izquierda; se
                // concatenan para no solaparse entre sí ni con la modebar.
                const partes = [];
                if (esPorPares(analyte)) partes.push('Z calculado dentro de cada grupo de pares');
                if (recortadas > 0) partes.push(`${recortadas} laboratorio(s) con |z| > ${Z_VIS}: barra al tope del eje, valor real en la etiqueta`);
                return partes.length ? [{
                    x: 0, y: 1.06, xref: 'paper', yref: 'paper', xanchor: 'left',
                    text: partes.join(' · '),
                    showarrow: false, font: { color: '#6c757d', size: 10 }
                }] : [];
            })()),
            ...(sinEvaluar.length ? [{
                x: 1, y: 1.06, xref: 'paper', yref: 'paper', xanchor: 'right',
                text: `Sin Z-Score (grupo de pares insuficiente): ${sinEvaluar.map(l => l.id).join(', ')}`,
                showarrow: false, font: { color: '#6c757d', size: 10 }
            }] : [])
        ]
    }, { responsive: true });
}

// ── Resumen por laboratorio ───────────────────────────────────────────
// Consolida el desempeño de cada laboratorio a través de todos los analitos.
//
// Excluye los analitos marcados como no concluyentes: su σ* inflada hace que
// casi todo resulte aceptable, de modo que incluirlos regalaría conformidad a
// todos los laboratorios por igual (hasta +5 puntos porcentuales) y la tabla
// dejaría de reflejar desempeño real.
// Adapta la consolidación ya calculada en Python al formato que usa la
// tabla. La exclusión de analitos no concluyentes y el criterio de que
// 'NE' no cuenta ya vienen aplicados desde consolidar_por_laboratorio().
function consolidarPorLab(data) {
    const g = data.desempeno_global || {};
    const filas = (g.por_laboratorio || []).map(r => ({
        id: r.id, a: r.A, c: r.C, i: r.I, n: r.n, pct: r.pct_conformidad
    }));
    const excluidosNombres = g.analitos_excluidos || [];
    const excluidos = data.analitos.filter(a => excluidosNombres.includes(a.nombre));
    const usables = data.analitos.filter(a => !excluidosNombres.includes(a.nombre));
    return { filas, usables, excluidos };
}

// Solo dibuja: las cifras vienen calculadas de calcular_zscore.py y
// validar_informe.py las recalcula antes de publicar. Aquí no se
// decide nada, para que la métrica no se clone con cada ronda.
function renderGlobalMetric(data) {
    const g = data.desempeno_global;
    if (!g || !g.laboratorios) return;

    document.getElementById('mg-cifra').textContent = g.pct_conformes.toFixed(1) + '%';
    document.getElementById('mg-detalle').innerHTML =
        `<strong>${g.conformes} de ${g.laboratorios}</strong> laboratorios<br>sin ningún resultado no conforme`;

    document.getElementById('mg-estratos').innerHTML = g.estratos.map(e => `
        <div class="estrato">
            <div class="nombre">${e.nombre}<small>${e.descripcion}</small></div>
            <div class="barra" title="${e.laboratorios} de ${g.laboratorios} laboratorios">
                <span style="width:${e.pct}%;background:${e.color}"></span>
            </div>
            <div class="valor"><strong>${e.laboratorios}</strong> · ${e.pct.toFixed(1)}%</div>
        </div>`).join('');

    document.getElementById('global-metric-note').innerHTML =
        `Esta métrica evalúa <strong>laboratorios</strong>, no resultados. Un laboratorio se ` +
        `considera satisfactorio solo si <strong>ninguno</strong> de sus analitos resultó no ` +
        `conforme: un resultado errado que llega a un paciente es una falla, con independencia ` +
        `de cuántos otros hayan salido bien. Por eso esta cifra es exigente y no coincide con ` +
        `el porcentaje de resultados aceptables del encabezado, que se calcula sobre analitos.`;

    // Sin esto, el porcentaje sugiere que la falla está repartida entre
    // todos. Está concentrada, y eso cambia la acción correctiva.
    const c = g.concentracion;
    if (c && c.no_conformes_total) {
        document.getElementById('global-metric-concentracion').innerHTML =
            `<strong>Las no conformidades están concentradas:</strong> ${c.laboratorios} laboratorios ` +
            `acumulan ${c.no_conformes} de los ${c.no_conformes_total} resultados no conformes de la ronda ` +
            `(${c.pct.toFixed(0)}%), sobre un total de ${g.laboratorios} participantes. ` +
            `La mayoría de los laboratorios con alguna falla presenta una sola; el esfuerzo de ` +
            `mejora debe dirigirse a los casos con desvío sistemático, no al conjunto.`;
    }

    document.getElementById('global-metric').style.display = 'block';
}

function renderLabTable(data) {
    const { filas, usables, excluidos } = consolidarPorLab(data);

    const nota = document.getElementById('lab-table-note');
    nota.innerHTML =
        `Consolidado de los ${usables.length} analitos con evaluación concluyente` +
        (excluidos.length
            ? `; se excluyen ${excluidos.map(a => a.nombre).join(' y ')}, cuya evaluación agrupada no es interpretable.`
            : '.') +
        ` <strong>El número de analitos evaluados varía entre laboratorios</strong> (de ` +
        `${Math.min(...filas.map(f => f.n))} a ${Math.max(...filas.map(f => f.n))}), porque cada uno reporta ` +
        `los que están dentro de su alcance. Por eso el porcentaje debe leerse siempre junto a esa columna: ` +
        `no es comparable un 100% sobre 10 analitos con un 100% sobre 24. ` +
        `Haga clic en los encabezados para reordenar.`;

    let orden = { campo: 'pct', asc: false };

    function pintar() {
        filas.sort((x, y) => {
            const v = orden.campo === 'id'
                ? x.id.localeCompare(y.id)
                : x[orden.campo] - y[orden.campo];
            if (v !== 0) return orden.asc ? v : -v;
            // Empates: primero el que evaluó más analitos. Muchos laboratorios
            // llegan a 100%, y dejar ese bloque en orden arbitrario pondría un
            // 100% sobre 9 analitos por encima de uno sobre 24. El código
            // desempata al final para que el orden sea estable entre recargas.
            return (y.n - x.n) || x.id.localeCompare(y.id);
        });

        document.getElementById('lab-tbody').innerHTML = filas.map(r => `
        <tr>
            <td class="cod">${r.id}</td>
            <td class="num">${r.n}</td>
            <td class="num">${r.a}</td>
            <td class="num">${r.c}</td>
            <td class="num">${r.i}</td>
            <td>
                <div class="conf-barra" title="${r.a} conformes, ${r.c} cuestionables, ${r.i} no conformes">
                    ${r.a ? `<span style="width:${r.a / r.n * 100}%;background:#1e7e34"></span>` : ''}
                    ${r.c ? `<span style="width:${r.c / r.n * 100}%;background:#b8860b"></span>` : ''}
                    ${r.i ? `<span style="width:${r.i / r.n * 100}%;background:#c62828"></span>` : ''}
                </div>
                <span class="conf-pct">${r.pct.toFixed(1)}% de ${r.n}</span>
            </td>
        </tr>`).join('');

        document.querySelectorAll('.tabla-labs th.sortable').forEach(th => {
            th.classList.remove('asc', 'desc');
            if (th.dataset.sort === orden.campo) th.classList.add(orden.asc ? 'asc' : 'desc');
        });
    }

    document.querySelectorAll('.tabla-labs th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const campo = th.dataset.sort;
            // Al cambiar de columna: el código arranca ascendente (A→Z) y las
            // métricas descendente, que es el sentido en que se quieren leer.
            orden = orden.campo === campo
                ? { campo, asc: !orden.asc }
                : { campo, asc: campo === 'id' };
            pintar();
        });
    });

    document.getElementById('lab-table-container').style.display = 'block';
    pintar();
}

function renderSummaryTable(analitos) {
    const container = document.getElementById('summary-table-container');
    container.style.display = 'block';
    container.id = 'resumen-tabla';
    const tbody = document.getElementById('summary-tbody');

    analitos.forEach(a => {
        const { A: countA, C: countC, I: countI } = a.conteos;

        // Un analito por grupo de pares ocupa una fila por grupo: no tiene un
        // X* único, y mostrar un promedio de ambos no describiría a ninguno.
        if (esPorPares(a)) {
            const evs = a.grupos.filter(g => g.evaluado);
            evs.forEach((g, k) => {
                const { A: cA, C: cC, I: cI } = g.conteos;
                const cvClass = g.cv > 30 ? 'cv-critical' : (g.cv > 15 ? 'cv-high' : '');
                tbody.innerHTML += `
                <tr>
                    <td>${k === 0 ? `<strong>${a.nombre}</strong>` : ''}
                        <div class="sub-grupo"><span class="punto-grupo"
                            style="background:${colorGrupo(a, g.nombre)}"></span>${g.nombre}</div></td>
                    <td>${g.n}</td>
                    <td>${g.valor_asignado} ${a.unidad}</td>
                    <td>${g.sd_robusta} ${a.unidad}</td>
                    <td class="${cvClass}">${g.cv}%</td>
                    <td>${cA}</td><td>${cC}</td><td>${cI}</td>
                </tr>`;
            });
            a.grupos.filter(g => !g.evaluado).forEach(g => {
                tbody.innerHTML += `
                <tr>
                    <td><div class="sub-grupo"><span class="punto-grupo"
                        style="background:#9aa3b2"></span>${g.nombre}</div></td>
                    <td>${g.n}</td>
                    <td colspan="6" class="sin-eval">Sin evaluar — ${g.motivo}</td>
                </tr>`;
            });
            return;
        }

        let cvClass = '';
        if (a.cv > 30) cvClass = 'cv-critical';
        else if (a.cv > 15) cvClass = 'cv-high';

        tbody.innerHTML += `
        <tr>
            <td><strong>${a.nombre}</strong></td>
            <td>${a.n}</td>
            <td>${a.valor_asignado} ${a.unidad}</td>
            <td>${a.sd_robusta} ${a.unidad}</td>
            <td class="${cvClass}">${a.cv}%</td>
            <td>${countA}</td>
            <td>${countC}</td>
            <td>${countI}</td>
        </tr>
    `;
    });
}

function renderCVAlerts(analitos) {
    const container = document.getElementById('cv-alerts');
    const highCV = analitos.filter(a => !esPorPares(a) && a.cv > 15).sort((a, b) => b.cv - a.cv);
    if (highCV.length === 0) return;

    let html = '<h3 style="color: var(--primary-color); margin-bottom: 1rem;">⚠️ Alertas de Coeficiente de Variación</h3>';
    highCV.forEach(a => {
        const isVeryHigh = a.cv > 30;
        const cls = isVeryHigh ? 'alert-danger' : 'alert-warning';
        const icon = isVeryHigh ? '🔴' : '⚠️';
        const nivel = isVeryHigh ? 'MUY ALTO' : 'ALTO';

        html += `<div class="alert-box ${cls}">
        ${icon} <strong>${a.nombre}</strong> — CV = ${a.cv}% (${nivel}).
        σ* = ${a.sd_robusta} ${a.unidad} sobre X* = ${a.valor_asignado} ${a.unidad}.
        Un CV elevado indica alta dispersión entre laboratorios.
    </div>`;
    });
    container.innerHTML = html;
}

// ── Dibujo perezoso ──────────────────────────────────────────────────────
// Plotly cuesta ~40 ms por gráfica y el informe tiene 53: dibujarlas todas al
// cargar bloquea ~2 s para mostrar las dos que caben en pantalla. Cada sección
// se dibuja al acercarse al viewport, con margen suficiente para que ya esté
// lista cuando el usuario llega. Los contenedores llevan `min-height` fija, así
// que la altura de la página no cambia al dibujarse y los anclas del índice
// siguen apuntando al sitio correcto.
const MARGEN_PREDIBUJO = '800px 0px';

function dibujarCuandoSeVean(data) {
    const secciones = data.analitos.map((a, i) => ({
        a, i, el: document.getElementById(safeId(a.nombre))
    })).filter(s => s.el);

    // El heatmap arranca oculto, y un elemento con display:none tiene tamaño
    // cero: IntersectionObserver nunca lo reportaría. Se muestra vacío con su
    // altura reservada y Plotly lo rellena cuando toca.
    const heatmap = document.getElementById('heatmap-section');
    if (heatmap) {
        heatmap.style.display = 'block';
        const lienzo = document.getElementById('heatmap-chart');
        if (lienzo) {
            lienzo.style.minHeight =
                Math.max(500, data.analitos.length * 30 + 120) + 'px';
        }
    }

    // Sin IntersectionObserver (navegador antiguo) se dibuja todo de una vez:
    // más lento, pero el informe nunca queda en blanco.
    if (!('IntersectionObserver' in window)) {
        requestAnimationFrame(() => {
            secciones.forEach(s => renderCharts(s.a, s.i));
            renderHeatmap(data);
        });
        return;
    }

    const obs = new IntersectionObserver((entradas, o) => {
        entradas.forEach(e => {
            if (!e.isIntersecting) return;
            o.unobserve(e.target);              // cada gráfica se dibuja una sola vez
            if (e.target === heatmap) {
                renderHeatmap(data);
            } else {
                const s = secciones.find(x => x.el === e.target);
                if (s) renderCharts(s.a, s.i);
            }
        });
    }, { rootMargin: MARGEN_PREDIBUJO });

    secciones.forEach(s => obs.observe(s.el));
    if (heatmap) obs.observe(heatmap);
}

function renderHeatmap(data) {
    document.getElementById('heatmap-section').style.display = 'block';

    // Collect all unique lab IDs sorted
    const allLabIds = new Set();
    data.analitos.forEach(a => a.laboratorios.forEach(l => allLabIds.add(l.id)));
    const labIds = [...allLabIds].sort();   // cod_anonimo: orden alfabetico
    const labLabels = labIds.map(id => id);

    // Analyte names (Y axis)
    const analyteNames = data.analitos.map(a => a.nombre);

    // Build Z-score matrix and custom hover text
    // Each row = one analyte, each col = one lab
    const zMatrix = [];
    const hoverMatrix = [];
    const CLAMP = 5;

    data.analitos.forEach(a => {
        const labMap = {};
        a.laboratorios.forEach(l => { labMap[l.id] = l; });

        const row = [];
        const hoverRow = [];
        labIds.forEach(id => {
            if (labMap[id] && labMap[id].z_score !== null) {
                const z = labMap[id].z_score;
                row.push(Math.max(-CLAMP, Math.min(CLAMP, z)));
                const clasif = labMap[id].clasificacion === 'A' ? LB.A
                    : labMap[id].clasificacion === 'C' ? LB.C : LB.I;
                hoverRow.push(
                    `${id}<br>${a.nombre}<br>Z-Score: ${z.toFixed(2)}<br>Resultado: ${labMap[id].resultado} ${a.unidad}<br>${clasif}`
                );
            } else {
                row.push(null);
                hoverRow.push(labMap[id]
                    ? `${id}<br>${a.nombre}<br>Resultado: ${labMap[id].resultado} ${a.unidad}<br>Sin evaluar (grupo de pares insuficiente)`
                    : `${id}<br>${a.nombre}<br>No participó`);
            }
        });
        zMatrix.push(row);
        hoverMatrix.push(hoverRow);
    });

    // Discrete colorscale aligned with bar charts:
    // |z| ≤ 2 → green, 2 < |z| < 3 → yellow, |z| ≥ 3 → red
    // Positions: z=-5→0, z=-3→0.2, z=-2→0.3, z=0→0.5, z=+2→0.7, z=+3→0.8, z=+5→1
    const colorscale = [
        [0, '#dc3545'],
        [0.19, '#dc3545'],
        [0.2, '#ffc107'],
        [0.29, '#ffc107'],
        [0.3, '#28a745'],
        [0.7, '#28a745'],
        [0.71, '#ffc107'],
        [0.8, '#ffc107'],
        [0.81, '#dc3545'],
        [1, '#dc3545']
    ];

    const traceHeatmap = {
        z: zMatrix,
        x: labLabels,
        y: analyteNames,
        type: 'heatmap',
        colorscale: colorscale,
        zmin: -CLAMP,
        zmax: CLAMP,
        hoverongaps: false,
        hovertext: hoverMatrix,
        hoverinfo: 'text',
        xgap: 2,
        ygap: 2,
        colorbar: {
            title: { text: 'Z-Score', side: 'right' },
            tickvals: [-5, -3, -2, 0, 2, 3, 5],
            ticktext: ['≤-5', '-3', '-2', '0', '+2', '+3', '≥+5'],
            len: 0.9
        },
        connectgaps: false
    };

    const heightCalc = Math.max(500, analyteNames.length * 30 + 120);

    Plotly.newPlot('heatmap-chart', [traceHeatmap], {
        title: { text: 'Desempeño por Laboratorio y Analito (Z-Score)', font: { size: 16, color: '#1a237e' } },
        xaxis: {
            title: 'Laboratorio',
            tickangle: -45,
            tickfont: { size: 10 },
            side: 'bottom'
        },
        yaxis: {
            title: '',
            tickfont: { size: 11 },
            automargin: true
        },
        height: heightCalc,
        margin: { l: 180, r: 80, t: 60, b: 100 },
        plot_bgcolor: '#f0f0f0',
        paper_bgcolor: 'white'
    }, { responsive: true });
}
