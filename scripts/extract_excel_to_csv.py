"""
Script para extraer datos del Excel de ensayos de aptitud a CSV consolidado.
Extrae todas las hojas con datos, limpia los valores y genera un CSV unificado.

Uso:
    conda activate concalab
    python scripts/extract_excel_to_csv.py
"""

import pandas as pd
import re
import os

# === CONFIGURACIÓN ===
EXCEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'data',
                          'LOS LABORATORIOS CON SUS PRUEBAS Y RESULTADOS.xlsx')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'ensayos_aptitud_consolidado.csv')


def extract_numeric(value):
    """Extrae el valor numérico de un string como '104 mg/dL' → 104.0"""
    if value is None:
        return None
    val_str = str(value).strip()
    # Buscar el primer número (entero o decimal)
    match = re.search(r'([\d]+\.?[\d]*)', val_str)
    if match:
        return float(match.group(1))
    return None


def extract_unit(value):
    """Extrae la unidad de un string como '104 mg/dL' → 'mg/dL'"""
    if value is None:
        return None
    val_str = str(value).strip()
    # Buscar texto después del número
    match = re.search(r'[\d]+\.?[\d]*\s*(.+)', val_str)
    if match:
        return match.group(1).strip()
    return None


def process_sheet(wb, sheet_name):
    """Procesa una hoja del Excel y retorna un DataFrame limpio."""
    try:
        df = pd.read_excel(wb, sheet_name=sheet_name, header=None)
    except Exception as e:
        print(f"  ⚠️ Error leyendo hoja '{sheet_name}': {e}")
        return None

    # Buscar la fila del encabezado (contiene '#: Laboratorio')
    header_row = None
    for idx, row in df.iterrows():
        row_str = ' '.join([str(v) for v in row.values if v is not None])
        if 'Laboratorio' in row_str:
            header_row = idx
            break

    if header_row is None:
        print(f"  ⚠️ No se encontró encabezado en '{sheet_name}'")
        return None

    # Buscar las columnas correctas por contenido del encabezado
    header = df.iloc[header_row]
    col_map = {}
    for col_idx, val in enumerate(header):
        if val is None:
            continue
        val_str = str(val).strip()
        if 'Laboratorio' in val_str:
            col_map['laboratorio'] = col_idx
        elif 'Mensurando' in val_str:
            col_map['mensurando'] = col_idx
        elif 'Muestra' in val_str:
            col_map['muestra'] = col_idx
        elif 'Resultado' in val_str:
            col_map['resultado'] = col_idx
        elif 'Evaluaci' in val_str:
            col_map['evaluacion'] = col_idx

    if 'laboratorio' not in col_map or 'resultado' not in col_map:
        print(f"  ⚠️ Columnas faltantes en '{sheet_name}': {col_map}")
        return None

    # Extraer datos (filas después del encabezado)
    data_rows = []
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]

        lab_val = row.iloc[col_map['laboratorio']]
        if lab_val is None or pd.isna(lab_val):
            continue

        # Número de laboratorio
        lab_num = str(lab_val).strip()
        try:
            lab_num = int(float(lab_num))
        except (ValueError, TypeError):
            continue

        # Resultado
        resultado_raw = row.iloc[col_map['resultado']] if 'resultado' in col_map else None
        resultado_num = extract_numeric(resultado_raw)
        unidad = extract_unit(resultado_raw)

        # Evaluación
        evaluacion = None
        if 'evaluacion' in col_map:
            eval_val = row.iloc[col_map['evaluacion']]
            if eval_val is not None and not pd.isna(eval_val):
                evaluacion = str(eval_val).strip().upper()

        # Muestra
        muestra = None
        if 'muestra' in col_map:
            m_val = row.iloc[col_map['muestra']]
            if m_val is not None and not pd.isna(m_val):
                muestra = str(m_val).strip()

        data_rows.append({
            'laboratorio': lab_num,
            'analito': sheet_name.strip(),
            'muestra': muestra,
            'resultado': resultado_num,
            'unidad': unidad,
            'evaluacion': evaluacion
        })

    if not data_rows:
        print(f"  ⚠️ Sin datos en '{sheet_name}'")
        return None

    return pd.DataFrame(data_rows)


def main():
    print("=" * 60)
    print("EXTRACCIÓN DE DATOS - CONCALAB")
    print("=" * 60)
    print(f"\n📂 Archivo: {os.path.basename(EXCEL_PATH)}")

    # Leer el workbook
    wb = pd.ExcelFile(EXCEL_PATH)
    print(f"📋 Hojas encontradas: {len(wb.sheet_names)}\n")

    all_data = []
    hojas_ok = 0
    hojas_vacias = 0

    for sheet_name in wb.sheet_names:
        print(f"  Procesando: {sheet_name}...", end=" ")
        result = process_sheet(wb, sheet_name)

        if result is not None and len(result) > 0:
            all_data.append(result)
            hojas_ok += 1
            print(f"✅ {len(result)} registros")
        else:
            hojas_vacias += 1
            print("❌ Vacía/Sin datos")

    if not all_data:
        print("\n❌ No se encontraron datos para exportar.")
        return

    # Consolidar
    df_final = pd.concat(all_data, ignore_index=True)

    # Ordenar por analito y laboratorio
    df_final = df_final.sort_values(['analito', 'laboratorio']).reset_index(drop=True)

    # Guardar CSV
    df_final.to_csv(OUTPUT_PATH, index=False, encoding='utf-8')

    print(f"\n{'=' * 60}")
    print(f"✅ RESUMEN")
    print(f"{'=' * 60}")
    print(f"  Hojas procesadas: {hojas_ok}")
    print(f"  Hojas vacías:     {hojas_vacias}")
    print(f"  Total registros:  {len(df_final)}")
    print(f"  Analitos únicos:  {df_final['analito'].nunique()}")
    print(f"  Labs únicos:      {df_final['laboratorio'].nunique()}")
    print(f"\n  📄 CSV guardado en: {os.path.abspath(OUTPUT_PATH)}")

    # Preview
    print(f"\n{'=' * 60}")
    print("PREVIEW (primeras 10 filas):")
    print(df_final.head(10).to_string(index=False))


if __name__ == '__main__':
    main()
