"""
Genera un reporte HTML interactivo con gráficos Plotly para cada analito:
  1. Histograma de resultados (valores originales en su unidad)
  2. Gráfico de barras vertical de Z-Score (labs en eje X, Z en eje Y, orden ascendente)

Uso:
    conda activate concalab
    python scripts/generate_report.py
"""

import pandas as pd
import numpy as np
import json
import os

# === CONFIGURACIÓN ===
CSV_INPUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'ensayos_con_zscore.csv')
HTML_OUTPUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'reporte_histogramas.html')


def color_by_zscore(z):
    if pd.isna(z):
        return '#999999'
    abs_z = abs(z)
    if abs_z <= 2.0:
        return '#28a745'
    elif abs_z < 3.0:
        return '#ffc107'
    else:
        return '#dc3545'


def make_histogram_js(div_id, valores, analito, unidad, valor_asignado, sd_robusta):
    """Genera JavaScript puro para el histograma usando Plotly.newPlot."""
    vals_list = [float(v) for v in valores if not pd.isna(v)]
    z2_low = valor_asignado - 2 * sd_robusta
    z2_high = valor_asignado + 2 * sd_robusta

    js = f"""
    Plotly.newPlot('{div_id}', [{{
        x: {json.dumps(vals_list)},
        type: 'histogram',
        nbinsx: {max(8, min(20, len(vals_list) // 2))},
        marker: {{
            color: 'rgba(26, 35, 126, 0.7)',
            line: {{ color: 'rgba(26, 35, 126, 1)', width: 1.5 }}
        }},
        hovertemplate: 'Rango: %{{x}}<br>Frecuencia: %{{y}}<extra></extra>'
    }}], {{
        title: {{ text: 'Distribución de Resultados — {analito} ({unidad})', font: {{ size: 15, color: '#1a237e' }} }},
        xaxis: {{ title: 'Resultado ({unidad})', gridcolor: '#eee' }},
        yaxis: {{ title: 'Frecuencia (n° de laboratorios)', gridcolor: '#eee', dtick: 1 }},
        height: 380,
        margin: {{ l: 60, r: 30, t: 50, b: 50 }},
        bargap: 0.05,
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        font: {{ family: 'Arial, sans-serif' }},
        shapes: [
            {{ type: 'line', x0: {valor_asignado}, x1: {valor_asignado}, y0: 0, y1: 1, yref: 'paper',
               line: {{ color: 'red', width: 2.5, dash: 'dash' }} }},
            {{ type: 'rect', x0: {z2_low}, x1: {z2_high}, y0: 0, y1: 1, yref: 'paper',
               fillcolor: 'rgba(40, 167, 69, 0.1)', line: {{ width: 0 }} }}
        ],
        annotations: [
            {{ x: {valor_asignado}, y: 1, yref: 'paper', text: 'X* = {valor_asignado:.1f}',
               showarrow: false, font: {{ color: 'red', size: 11 }}, xanchor: 'left', xshift: 5 }}
        ]
    }}, {{ responsive: true }});
    """
    return js


def make_bar_zscore_js(div_id, df_sorted, analito):
    """Genera JavaScript puro para barras verticales de Z-Score."""
    lab_labels = [f'Lab {int(l)}' for l in df_sorted['laboratorio']]
    z_values = [float(z) for z in df_sorted['z_score']]
    colors = [color_by_zscore(z) for z in z_values]
    resultados = [float(r) for r in df_sorted['resultado']]
    unidades = list(df_sorted['unidad'].values)

    # Texto hover personalizado
    hover_texts = [
        f'Lab {int(l)}<br>Z-Score: {z:.2f}<br>Resultado: {r:.2f} {u}'
        for l, z, r, u in zip(df_sorted['laboratorio'], z_values, resultados, unidades)
    ]

    y_min = min(min(z_values) - 1, -4)
    y_max = max(max(z_values) + 1, 4)

    js = f"""
    Plotly.newPlot('{div_id}', [{{
        x: {json.dumps(lab_labels)},
        y: {json.dumps(z_values)},
        type: 'bar',
        orientation: 'v',
        marker: {{
            color: {json.dumps(colors)},
            line: {{ color: 'rgba(0,0,0,0.15)', width: 0.5 }}
        }},
        text: {json.dumps([f'{z:.2f}' for z in z_values])},
        textposition: 'outside',
        textfont: {{ size: 8 }},
        hovertext: {json.dumps(hover_texts)},
        hoverinfo: 'text'
    }}], {{
        title: {{ text: 'Z-Score por Laboratorio — {analito}', font: {{ size: 15, color: '#1a237e' }} }},
        xaxis: {{ title: 'Laboratorio', tickangle: -45, tickfont: {{ size: 9 }}, gridcolor: '#eee' }},
        yaxis: {{ title: 'Z-Score', range: [{y_min}, {y_max}], gridcolor: '#eee', zeroline: false }},
        height: 450,
        margin: {{ l: 60, r: 60, t: 50, b: 100 }},
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        font: {{ family: 'Arial, sans-serif' }},
        shapes: [
            {{ type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 0, y1: 0, line: {{ color: '#666', width: 1 }} }},
            {{ type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 2, y1: 2, line: {{ color: 'orange', width: 1.5, dash: 'dash' }} }},
            {{ type: 'line', x0: 0, x1: 1, xref: 'paper', y0: -2, y1: -2, line: {{ color: 'orange', width: 1.5, dash: 'dash' }} }},
            {{ type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 3, y1: 3, line: {{ color: 'red', width: 1.5, dash: 'dot' }} }},
            {{ type: 'line', x0: 0, x1: 1, xref: 'paper', y0: -3, y1: -3, line: {{ color: 'red', width: 1.5, dash: 'dot' }} }},
            {{ type: 'rect', x0: 0, x1: 1, xref: 'paper', y0: -2, y1: 2,
               fillcolor: 'rgba(40, 167, 69, 0.05)', line: {{ width: 0 }} }}
        ],
        annotations: [
            {{ x: 1.02, xref: 'paper', y: 2, text: 'z=+2', showarrow: false, font: {{ color: 'orange', size: 9 }} }},
            {{ x: 1.02, xref: 'paper', y: -2, text: 'z=-2', showarrow: false, font: {{ color: 'orange', size: 9 }} }},
            {{ x: 1.02, xref: 'paper', y: 3, text: 'z=+3', showarrow: false, font: {{ color: 'red', size: 9 }} }},
            {{ x: 1.02, xref: 'paper', y: -3, text: 'z=-3', showarrow: false, font: {{ color: 'red', size: 9 }} }}
        ]
    }}, {{ responsive: true }});
    """
    return js


def main():
    print("=" * 60)
    print("  GENERACIÓN DE REPORTE VISUAL — Plotly")
    print("=" * 60)

    df = pd.read_csv(CSV_INPUT)
    print(f"\n📂 Datos: {len(df)} registros, {df['analito'].nunique()} analitos")

    analitos = sorted(df['analito'].unique())

    # === HTML ===
    html = []
    html.append("""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de Ensayos de Aptitud — CONCALAB-UASD</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Arial', sans-serif; background: #f5f5f5; color: #333; }
        .header {
            background: linear-gradient(135deg, #1a237e, #3949ab);
            color: white; padding: 2rem; text-align: center;
        }
        .header h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
        .header p { opacity: 0.85; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem 1rem; }
        .legend {
            background: white; padding: 1rem 1.5rem; border-radius: 8px;
            margin-bottom: 2rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            display: flex; gap: 2rem; flex-wrap: wrap; align-items: center;
        }
        .legend-item { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; }
        .legend-dot { width: 16px; height: 16px; border-radius: 3px; display: inline-block; }
        .nav-toc {
            background: white; padding: 1.5rem; border-radius: 8px;
            margin-bottom: 2rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }
        .nav-toc h3 { margin-bottom: 0.75rem; color: #1a237e; }
        .nav-toc ul { list-style: none; display: flex; flex-wrap: wrap; gap: 0.5rem; }
        .nav-toc a {
            display: inline-block; padding: 0.4rem 0.8rem;
            background: #e8eaf6; color: #1a237e; border-radius: 4px;
            text-decoration: none; font-size: 0.85rem;
        }
        .nav-toc a:hover { background: #3949ab; color: white; }
        .chart-section {
            background: white; padding: 1.5rem; border-radius: 8px;
            margin-bottom: 2rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }
        .chart-section h2 {
            color: #1a237e; font-size: 1.3rem;
            border-bottom: 2px solid #3949ab;
            padding-bottom: 0.5rem; margin-bottom: 1rem;
        }
        .stats-row { display: flex; gap: 0.8rem; flex-wrap: wrap; margin-bottom: 1rem; }
        .stat-card {
            background: #f5f5f5; padding: 0.5rem 0.8rem; border-radius: 6px;
            font-size: 0.85rem; flex: 1; min-width: 130px;
        }
        .stat-card strong { color: #1a237e; }
        .summary-section {
            background: white; padding: 2rem; border-radius: 8px;
            margin-bottom: 2rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }
        .summary-section h2 {
            color: #1a237e; font-size: 1.4rem;
            border-bottom: 2px solid #3949ab;
            padding-bottom: 0.5rem; margin-bottom: 1.5rem;
        }
        .summary-section h3 {
            color: #1a237e; font-size: 1.1rem;
            margin: 1.5rem 0 0.75rem 0;
        }
        .summary-table {
            width: 100%; border-collapse: collapse; font-size: 0.85rem;
            margin-bottom: 1.5rem;
        }
        .summary-table th {
            background: #1a237e; color: white; padding: 0.6rem 0.8rem;
            text-align: left; font-weight: 600;
        }
        .summary-table td {
            padding: 0.5rem 0.8rem; border-bottom: 1px solid #eee;
        }
        .summary-table tr:hover { background: #f5f5f5; }
        .alert-box {
            padding: 1rem 1.2rem; border-radius: 8px; margin-bottom: 0.8rem;
            font-size: 0.9rem;
        }
        .alert-warning {
            background: #fff3cd; border-left: 4px solid #ffc107; color: #856404;
        }
        .alert-danger {
            background: #f8d7da; border-left: 4px solid #dc3545; color: #721c24;
        }
        .alert-success {
            background: #d4edda; border-left: 4px solid #28a745; color: #155724;
        }
        .overall-stats {
            display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0;
        }
        .overall-card {
            flex: 1; min-width: 200px; padding: 1.2rem; border-radius: 8px;
            text-align: center; color: white; font-size: 1.1rem;
        }
        .overall-card .number { font-size: 2rem; font-weight: bold; }
        .overall-card .label { font-size: 0.85rem; opacity: 0.9; }
        .methodology {
            background: #e8eaf6; padding: 1rem 1.5rem; border-radius: 8px;
            font-size: 0.85rem; margin-top: 1.5rem; line-height: 1.6;
        }
        .methodology strong { color: #1a237e; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔬 Reporte de Ensayos de Aptitud</h1>
        <p>CONCALAB-UASD — Metodología ISO/IEC 17043 &amp; ISO 13528</p>
    </div>
    <div class="container">
        <div class="legend">
            <strong>Leyenda Z-Score:</strong>
            <span class="legend-item"><span class="legend-dot" style="background:#28a745;"></span> Aceptable (|z| ≤ 2)</span>
            <span class="legend-item"><span class="legend-dot" style="background:#ffc107;"></span> Cuestionable (2 &lt; |z| &lt; 3)</span>
            <span class="legend-item"><span class="legend-dot" style="background:#dc3545;"></span> Inaceptable (|z| ≥ 3)</span>
        </div>
""")

    # Índice
    html.append('<div class="nav-toc"><h3>📋 Índice de Analitos</h3><ul>')
    for analito in analitos:
        safe_id = analito.replace(' ', '-').replace('(', '').replace(')', '').replace('.', '')
        html.append(f'<li><a href="#{safe_id}">{analito}</a></li>')
    html.append('<li><a href="#resumen-hallazgos" style="background:#1a237e;color:white;">📊 Resumen</a></li>')
    html.append('</ul></div>')

    # Gráficos + recolectar stats
    chart_id = 0
    all_stats = []
    total_a = 0
    total_c = 0
    total_i = 0
    total_n = 0

    for analito in analitos:
        df_analito = df[df['analito'] == analito]
        df_valid = df_analito.dropna(subset=['resultado', 'z_score']).copy()

        if len(df_valid) == 0:
            continue

        unidad = df_valid['unidad'].iloc[0]
        valor_asignado = float(df_valid['valor_asignado'].iloc[0])
        sd_robusta = float(df_valid['sd_robusta'].iloc[0])
        n = len(df_valid)
        aceptables = len(df_valid[df_valid['clasificacion_calculada'] == 'A'])
        cuestionables = len(df_valid[df_valid['clasificacion_calculada'] == 'C'])
        inaceptables = len(df_valid[df_valid['clasificacion_calculada'] == 'I'])
        cv = (sd_robusta / valor_asignado * 100) if valor_asignado != 0 else 0
        safe_id = analito.replace(' ', '-').replace('(', '').replace(')', '').replace('.', '')

        all_stats.append({
            'analito': analito, 'n': n, 'unidad': unidad,
            'valor_asignado': valor_asignado, 'sd_robusta': sd_robusta,
            'cv': cv, 'aceptables': aceptables,
            'cuestionables': cuestionables, 'inaceptables': inaceptables
        })
        total_a += aceptables
        total_c += cuestionables
        total_i += inaceptables
        total_n += n

        print(f"  📊 {analito}...", end=" ")

        hist_id = f'hist{chart_id}'
        bar_id = f'bar{chart_id}'

        # Generar JS para cada gráfico
        hist_js = make_histogram_js(hist_id, df_valid['resultado'].values, analito, unidad, valor_asignado, sd_robusta)
        df_sorted = df_valid.sort_values('z_score').reset_index(drop=True)
        bar_js = make_bar_zscore_js(bar_id, df_sorted, analito)

        html.append(f'''
        <div class="chart-section" id="{safe_id}">
            <h2>🧪 {analito}</h2>
            <div class="stats-row">
                <div class="stat-card"><strong>n:</strong> {n} labs</div>
                <div class="stat-card"><strong>X*:</strong> {valor_asignado:.2f} {unidad}</div>
                <div class="stat-card"><strong>σ*:</strong> {sd_robusta:.2f} {unidad}</div>
                <div class="stat-card"><strong>CV:</strong> {cv:.1f}%</div>
                <div class="stat-card">✅ {aceptables} ⚠️ {cuestionables} ❌ {inaceptables}</div>
            </div>
            <div id="{hist_id}" style="width:100%;"></div>
            <div id="{bar_id}" style="width:100%; margin-top: 1rem;"></div>
        </div>
        <script>
        {hist_js}
        {bar_js}
        </script>
''')
        chart_id += 1
        print(f"✅ ({n} labs)")

    # === SECCIÓN DE RESUMEN ===
    pct_a = (total_a / total_n * 100) if total_n > 0 else 0
    pct_c = (total_c / total_n * 100) if total_n > 0 else 0
    pct_i = (total_i / total_n * 100) if total_n > 0 else 0

    html.append(f'''
    <div class="summary-section" id="resumen-hallazgos">
        <h2>📊 Resumen de Hallazgos</h2>

        <h3>Desempeño General</h3>
        <div class="overall-stats">
            <div class="overall-card" style="background: #28a745;">
                <div class="number">{total_a}</div>
                <div class="label">Aceptables ({pct_a:.1f}%)</div>
            </div>
            <div class="overall-card" style="background: #ffc107; color: #333;">
                <div class="number">{total_c}</div>
                <div class="label">Cuestionables ({pct_c:.1f}%)</div>
            </div>
            <div class="overall-card" style="background: #dc3545;">
                <div class="number">{total_i}</div>
                <div class="label">Inaceptables ({pct_i:.1f}%)</div>
            </div>
            <div class="overall-card" style="background: #1a237e;">
                <div class="number">{total_n}</div>
                <div class="label">Total Evaluaciones</div>
            </div>
        </div>
    ''')

    # Alertas de CV alto
    cv_high = [s for s in all_stats if s['cv'] > 15]
    if cv_high:
        html.append('<h3>⚠️ Alertas de Coeficiente de Variación</h3>')
        for s in sorted(cv_high, key=lambda x: -x['cv']):
            if s['cv'] > 30:
                alert_class = 'alert-danger'
                icon = '🔴'
                nivel = 'MUY ALTO'
            else:
                alert_class = 'alert-warning'
                icon = '⚠️'
                nivel = 'ALTO'
            html.append(f'''
            <div class="alert-box {alert_class}">
                {icon} <strong>{s['analito']}</strong> — CV = {s['cv']:.1f}% ({nivel}).
                σ* = {s['sd_robusta']:.2f} {s['unidad']} sobre X* = {s['valor_asignado']:.2f} {s['unidad']}.
                Un CV elevado indica alta dispersión entre laboratorios, lo que sugiere diferencias
                significativas en métodos, calibración o procedimientos analíticos.
            </div>''')
    else:
        html.append('''
        <div class="alert-box alert-success">
            ✅ Todos los analitos presentan un Coeficiente de Variación dentro de rangos aceptables (CV ≤ 15%).
        </div>''')

    # Tabla resumen
    html.append('''
        <h3>Tabla Estadística por Analito</h3>
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
                    <th>% Aceptable</th>
                </tr>
            </thead>
            <tbody>
    ''')

    for s in all_stats:
        pct_ok = (s['aceptables'] / s['n'] * 100) if s['n'] > 0 else 0
        cv_style = ''
        if s['cv'] > 30:
            cv_style = 'style="color: #dc3545; font-weight: bold;"'
        elif s['cv'] > 15:
            cv_style = 'style="color: #856404; font-weight: bold;"'

        html.append(f'''
                <tr>
                    <td><strong>{s['analito']}</strong></td>
                    <td>{s['n']}</td>
                    <td>{s['valor_asignado']:.2f} {s['unidad']}</td>
                    <td>{s['sd_robusta']:.2f} {s['unidad']}</td>
                    <td {cv_style}>{s['cv']:.1f}%</td>
                    <td>{s['aceptables']}</td>
                    <td>{s['cuestionables']}</td>
                    <td>{s['inaceptables']}</td>
                    <td>{pct_ok:.0f}%</td>
                </tr>
        ''')

    html.append('''
            </tbody>
        </table>
    ''')

    # Metodología
    html.append(f'''
        <div class="methodology">
            <strong>Metodología:</strong><br>
            • <strong>Valor asignado (X*):</strong> Media robusta calculada con Algoritmo A de ISO 13528:2015<br>
            • <strong>Desviación estándar (σ*):</strong> SD robusta calculada con Algoritmo S de ISO 13528:2015<br>
            • <strong>Z-Score:</strong> z = (x − X*) / σ*, donde x es el resultado del laboratorio<br>
            • <strong>Criterios:</strong> |z| ≤ 2 → Aceptable | 2 &lt; |z| &lt; 3 → Cuestionable | |z| ≥ 3 → Inaceptable<br>
            • <strong>CV umbral:</strong> Se alerta cuando CV &gt; 15% (alto) o CV &gt; 30% (muy alto)
        </div>
    </div>
    ''')

    html.append('</div></body></html>')

    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html))

    print(f"\n{'=' * 60}")
    print(f"✅ Reporte generado: {os.path.abspath(HTML_OUTPUT)}")


if __name__ == '__main__':
    main()

