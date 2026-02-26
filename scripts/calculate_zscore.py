"""
Script de análisis y cálculo de Z-Score según ISO/IEC 17043 & ISO 13528.

Metodología:
  Z = (x - X*) / σ*

  Donde:
    x   = resultado del laboratorio
    X*  = valor asignado (robust mean, Algoritmo A de ISO 13528)
    σ*  = desviación estándar para evaluación (robust SD, Algoritmo S de ISO 13528)

  Criterios de evaluación:
    |z| ≤ 2.0  → Aceptable (A)
    2.0 < |z| < 3.0 → Cuestionable (C)
    |z| ≥ 3.0  → Inaceptable (I)

Uso:
    conda activate concalab
    python scripts/calculate_zscore.py
"""

import pandas as pd
import numpy as np
import json
import os

# === CONFIGURACIÓN ===
CSV_INPUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'ensayos_aptitud_consolidado.csv')
CSV_OUTPUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'ensayos_con_zscore.csv')
REPORT_OUTPUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'reporte_estadistico.txt')
JSON_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'informes')

# Código del ensayo actual
CODIGO_ENSAYO = 'EA-001-2025'


# ====================================================================
# ALGORITMOS ISO 13528 (Estadística Robusta)
# ====================================================================

def robust_mean_sd(data, max_iterations=50, tol=1e-6):
    """
    Calcula la media robusta (X*) y desviación estándar robusta (σ*)
    usando los Algoritmos A y S de ISO 13528:2015.

    Estos algoritmos son resistentes a valores atípicos (outliers),
    lo cual es fundamental en ensayos de aptitud donde algunos
    laboratorios pueden reportar valores muy alejados.

    Parámetros:
        data: array de resultados numéricos
        max_iterations: máximo de iteraciones para convergencia
        tol: tolerancia para convergencia

    Retorna:
        x_star: media robusta (valor asignado)
        s_star: desviación estándar robusta
    """
    x = np.sort(data.copy())
    n = len(x)

    if n < 3:
        return np.mean(x), np.std(x, ddof=1) if n > 1 else 0.0

    # Paso 1: Valores iniciales
    x_star = np.median(x)
    s_star = 1.483 * np.median(np.abs(x - x_star))

    if s_star == 0:
        # Si la MAD es 0, usar rango intercuartílico
        q75, q25 = np.percentile(x, [75, 25])
        s_star = (q75 - q25) / 1.349
        if s_star == 0:
            s_star = np.std(x, ddof=1)

    # Paso 2: Iterar hasta convergencia
    for iteration in range(max_iterations):
        delta = 1.5 * s_star

        # Winsorizar: recortar valores extremos
        x_winsor = np.clip(x, x_star - delta, x_star + delta)

        # Calcular nuevos estimadores
        x_star_new = np.mean(x_winsor)
        s_star_new = 1.134 * np.sqrt(np.sum((x_winsor - x_star_new) ** 2) / (n - 1))

        # Verificar convergencia
        if abs(x_star_new - x_star) < tol and abs(s_star_new - s_star) < tol:
            break

        x_star = x_star_new
        s_star = s_star_new

    return x_star, s_star


def calculate_zscore(result, assigned_value, std_dev):
    """Calcula el Z-Score: z = (x - X*) / σ*"""
    if std_dev == 0 or pd.isna(result):
        return np.nan
    return (result - assigned_value) / std_dev


def classify_zscore(z):
    """
    Clasifica el Z-Score según ISO/IEC 17043:
      |z| ≤ 2.0  → A (Aceptable/Satisfactorio)
      2.0 < |z| < 3.0 → C (Cuestionable/Advertencia)
      |z| ≥ 3.0  → I (Inaceptable/No satisfactorio)
    """
    if pd.isna(z):
        return 'NR'  # No Reportado
    abs_z = abs(z)
    if abs_z <= 2.0:
        return 'A'
    elif abs_z < 3.0:
        return 'C'
    else:
        return 'I'


# ====================================================================
# PROCESAMIENTO PRINCIPAL
# ====================================================================

def main():
    print("=" * 70)
    print("  CÁLCULO DE Z-SCORE — ISO/IEC 17043 & ISO 13528")
    print("  CONCALAB-UASD — Ensayos de Aptitud")
    print("=" * 70)

    # 1. Cargar datos
    df = pd.read_csv(CSV_INPUT)
    print(f"\n📂 Datos cargados: {len(df)} registros")
    print(f"   Analitos: {df['analito'].nunique()}")
    print(f"   Laboratorios: {df['laboratorio'].nunique()}")

    # 2. Eliminar filas sin resultado
    df_clean = df.dropna(subset=['resultado']).copy()
    eliminados = len(df) - len(df_clean)
    if eliminados > 0:
        print(f"   ⚠️ {eliminados} registros sin resultado eliminados")

    # 3. Calcular estadísticas robustas por analito
    print(f"\n{'=' * 70}")
    print(f"  ESTADÍSTICAS ROBUSTAS POR ANALITO (ISO 13528)")
    print(f"{'=' * 70}")
    print(f"{'Analito':<28} {'n':>3} {'Media Clás.':>11} {'Media Rob.':>11} "
          f"{'SD Clás.':>9} {'SD Rob.':>9} {'Unidad':<8}")
    print("-" * 90)

    stats_list = []
    results_with_z = []

    analitos = sorted(df_clean['analito'].unique())

    for analito in analitos:
        subset = df_clean[df_clean['analito'] == analito]
        values = subset['resultado'].values
        unidad = subset['unidad'].dropna().iloc[0] if not subset['unidad'].dropna().empty else '?'
        n = len(values)

        # Estadísticas clásicas
        mean_classic = np.mean(values)
        sd_classic = np.std(values, ddof=1)

        # Estadísticas robustas (ISO 13528)
        x_star, s_star = robust_mean_sd(values)

        stats_list.append({
            'analito': analito,
            'n': n,
            'unidad': unidad,
            'media_clasica': round(mean_classic, 2),
            'sd_clasica': round(sd_classic, 2),
            'media_robusta': round(x_star, 2),
            'sd_robusta': round(s_star, 2),
            'cv_pct': round((s_star / x_star * 100), 1) if x_star != 0 else 0
        })

        print(f"{analito:<28} {n:>3} {mean_classic:>11.2f} {x_star:>11.2f} "
              f"{sd_classic:>9.2f} {s_star:>9.2f} {unidad:<8}")

        # 4. Calcular Z-Score para cada laboratorio
        for _, row in subset.iterrows():
            z = calculate_zscore(row['resultado'], x_star, s_star)
            clasificacion = classify_zscore(z)

            results_with_z.append({
                'laboratorio': row['laboratorio'],
                'analito': analito,
                'muestra': row['muestra'],
                'resultado': row['resultado'],
                'unidad': unidad,
                'valor_asignado': round(x_star, 2),
                'sd_robusta': round(s_star, 2),
                'z_score': round(z, 2) if not pd.isna(z) else None,
                'clasificacion_calculada': clasificacion,
                'clasificacion_original': row['evaluacion']
            })

    # 5. Crear DataFrame final
    df_zscore = pd.DataFrame(results_with_z)

    # 6. Guardar CSV con Z-Scores
    df_zscore.to_csv(CSV_OUTPUT, index=False, encoding='utf-8')

    # 7. Resumen de desempeño
    print(f"\n{'=' * 70}")
    print(f"  RESUMEN DE DESEMPEÑO")
    print(f"{'=' * 70}")

    total = len(df_zscore[df_zscore['z_score'].notna()])
    aceptables = len(df_zscore[df_zscore['clasificacion_calculada'] == 'A'])
    cuestionables = len(df_zscore[df_zscore['clasificacion_calculada'] == 'C'])
    inaceptables = len(df_zscore[df_zscore['clasificacion_calculada'] == 'I'])

    print(f"  ✅ Aceptables (|z| ≤ 2):     {aceptables} ({aceptables/total*100:.1f}%)")
    print(f"  ⚠️  Cuestionables (2 < |z| < 3): {cuestionables} ({cuestionables/total*100:.1f}%)")
    print(f"  ❌ Inaceptables (|z| ≥ 3):    {inaceptables} ({inaceptables/total*100:.1f}%)")

    # 8. Comparación con clasificación original del Excel
    df_compare = df_zscore.dropna(subset=['z_score', 'clasificacion_original'])
    # Mapear: original A → A, original I → podría ser C o I
    coincidencias = 0
    discrepancias = []
    for _, row in df_compare.iterrows():
        orig = row['clasificacion_original']
        calc = row['clasificacion_calculada']
        if orig == 'A' and calc == 'A':
            coincidencias += 1
        elif orig == 'I' and calc in ('C', 'I'):
            coincidencias += 1
        else:
            coincidencias += 0
            discrepancias.append(row)

    print(f"\n  📊 Comparación con clasificación original del Excel:")
    print(f"     Coincidencias: {coincidencias}/{len(df_compare)} ({coincidencias/len(df_compare)*100:.1f}%)")
    print(f"     Discrepancias: {len(discrepancias)}")

    if discrepancias:
        print(f"\n  Principales discrepancias (máx 10):")
        for d in discrepancias[:10]:
            print(f"    Lab {int(d['laboratorio']):>3} | {d['analito']:<25} | "
                  f"Resultado: {d['resultado']:>8} | Z: {d['z_score']:>6} | "
                  f"Original: {d['clasificacion_original']} → Calculado: {d['clasificacion_calculada']}")

    # 9. Guardar reporte
    stats_df = pd.DataFrame(stats_list)

    with open(REPORT_OUTPUT, 'w', encoding='utf-8') as f:
        f.write("REPORTE ESTADÍSTICO - ENSAYOS DE APTITUD CONCALAB-UASD\n")
        f.write("Metodología: ISO/IEC 17043 & ISO 13528 (Estadística Robusta)\n")
        f.write("=" * 70 + "\n\n")
        f.write("PARÁMETROS ESTADÍSTICOS POR ANALITO:\n\n")
        f.write(stats_df.to_string(index=False))
        f.write(f"\n\n{'=' * 70}\n")
        f.write(f"RESUMEN GENERAL:\n")
        f.write(f"  Total evaluaciones: {total}\n")
        f.write(f"  Aceptables:    {aceptables} ({aceptables/total*100:.1f}%)\n")
        f.write(f"  Cuestionables: {cuestionables} ({cuestionables/total*100:.1f}%)\n")
        f.write(f"  Inaceptables:  {inaceptables} ({inaceptables/total*100:.1f}%)\n")

    # 10. Exportar JSON para el informe web
    json_path = export_json(CODIGO_ENSAYO, stats_list, results_with_z,
                            total, aceptables, cuestionables, inaceptables)

    print(f"\n{'=' * 70}")
    print(f"  ARCHIVOS GENERADOS")
    print(f"{'=' * 70}")
    print(f"  📄 {os.path.basename(CSV_OUTPUT)} ({len(df_zscore)} registros)")
    print(f"  📄 {os.path.basename(REPORT_OUTPUT)}")
    print(f"  📄 {os.path.basename(json_path)} (JSON para informe web)")
    print(f"\nValores de referencia: Media Robusta (Algoritmo A, ISO 13528)")
    print(f"Dispersión: SD Robusta (Algoritmo S, ISO 13528)")


def export_json(codigo, stats_list, results_with_z, total, aceptables, cuestionables, inaceptables):
    """
    Exporta los datos procesados como JSON estructurado para que
    el informe web (Plotly.js) los consuma con fetch().
    """
    os.makedirs(JSON_OUTPUT_DIR, exist_ok=True)

    # Organizar resultados por analito
    analitos_data = []
    for stat in stats_list:
        analito_name = stat['analito']
        labs = [
            r for r in results_with_z
            if r['analito'] == analito_name and r['z_score'] is not None
        ]
        labs_sorted = sorted(labs, key=lambda x: x['z_score'])

        analitos_data.append({
            'nombre': analito_name,
            'unidad': stat['unidad'],
            'n': stat['n'],
            'valor_asignado': stat['media_robusta'],
            'sd_robusta': stat['sd_robusta'],
            'cv': stat['cv_pct'],
            'laboratorios': [
                {
                    'id': int(l['laboratorio']),
                    'resultado': l['resultado'],
                    'z_score': l['z_score'],
                    'clasificacion': l['clasificacion_calculada']
                }
                for l in labs_sorted
            ]
        })

    report_data = {
        'codigo': codigo,
        'fecha': pd.Timestamp.now().strftime('%Y-%m-%d'),
        'metodologia': 'ISO/IEC 17043 & ISO 13528 (Estadística Robusta)',
        'analitos': analitos_data,
        'resumen': {
            'total': total,
            'aceptables': aceptables,
            'cuestionables': cuestionables,
            'inaceptables': inaceptables
        }
    }

    json_path = os.path.join(JSON_OUTPUT_DIR, f'{codigo}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"\n  📦 JSON exportado: {os.path.abspath(json_path)}")
    return json_path


if __name__ == '__main__':
    main()
