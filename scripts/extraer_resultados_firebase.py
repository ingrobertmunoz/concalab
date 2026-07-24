"""
Extrae los resultados de una ronda desde Firestore a CSV (Fase 0 del pipeline).

Sustituye a extract_excel_to_csv.py: desde EA-001-2026 los laboratorios
reportan por el formulario web, así que la fuente es la colección
'resultados_generales' y no un Excel.

Salida: support/ensayos_<codigo>.csv

IMPORTANTE — por qué la salida va en support/ y NO en data/:
  1. data/ se despliega a GitHub Pages; support/ no. Este CSV lleva 'metodo' e
     'instrumento' en texto libre (ej. "FUJIFILM DRI-CHEMNX700"). Con ~37 labs
     participantes, publicar la relación cod_anonimo → modelo de equipo permitiría
     re-identificar laboratorios y debilitaría el anonimato de los informes.
  2. Son datos crudos sin revisar: incluyen errores de transcripción y de muestra
     que aún no se han evaluado. No deben quedar expuestos como archivo estático.
  El CSV es regenerable desde Firestore (fuente de verdad), por eso va en .gitignore.

  Aun así el CSV nunca escribe el nombre real del laboratorio, solo 'cod_anonimo'
  (ver 'Regla de anonimización' en CLAUDE.md); el script aborta si se colara un
  campo identificable.

Los valores salen TAL CUAL los reportó el laboratorio ('resultado_raw',
'unidad_raw'), sin convertir ni corregir. La normalización es la Fase 1.

Requisitos:
  conda activate concalab
  pip install firebase-admin

Uso:
  python scripts/extraer_resultados_firebase.py                  # ronda activa
  python scripts/extraer_resultados_firebase.py --codigo EA-001-2026
"""

import os
import sys
import csv
import json
import argparse
import statistics
from collections import defaultdict

import firebase_admin
from firebase_admin import credentials, firestore

CREDS_PATH  = "support/concalab-uasd-64ff4-firebase-adminsdk-fbsvc-c400cdf10b.json"
CONFIG_PATH = "data/config.json"
COLECCION   = "resultados_generales"
SALIDA_DIR  = "support"   # NO usar data/: se despliega a GitHub Pages (ver encabezado)

# Columnas del CSV. No incluye 'laboratorio' a propósito (ver nota de anonimización).
COLUMNAS = [
    "cod_anonimo", "categoria", "analito",
    "metodo", "instrumento", "resultado_raw", "unidad_raw", "fecha_reporte",
]

# Cualquier campo del documento que pueda de-anonimizar al laboratorio.
CAMPOS_PROHIBIDOS = {"laboratorio", "correo", "representante", "telefono", "uid_lab", "cod_interno"}


def ronda_activa():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)["ronda_activa"]


def conectar():
    if not os.path.exists(CREDS_PATH):
        sys.exit(f"ERROR: no se encontró la clave de servicio en {CREDS_PATH}")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(CREDS_PATH))
    return firestore.client()


def extraer(db, codigo):
    """Aplana resultados[] de cada documento en filas analito-por-laboratorio."""
    docs = db.collection(COLECCION).where("codigo_ensayo", "==", codigo).stream()

    filas, sin_codigo, vacios = [], 0, 0
    for d in docs:
        doc = d.to_dict()
        cod = (doc.get("cod_anonimo") or "").strip()
        if not cod:
            # Sin código anónimo no se puede publicar el resultado de forma trazable.
            sin_codigo += 1
            continue

        fecha = doc.get("fecha_reporte", "")
        for r in doc.get("resultados", []) or []:
            resultado = str(r.get("result", "")).strip()
            if not resultado:
                vacios += 1
                continue
            filas.append({
                "cod_anonimo":   cod,
                "categoria":     str(r.get("categoria", "")).strip(),
                "analito":       str(r.get("analyte", "")).strip(),
                "metodo":        str(r.get("method", "")).strip(),
                "instrumento":   str(r.get("instrument", "")).strip(),
                "resultado_raw": resultado,
                "unidad_raw":    str(r.get("unit", "")).strip(),
                "fecha_reporte": fecha,
            })

    filas.sort(key=lambda f: (f["categoria"], f["analito"], f["cod_anonimo"]))
    return filas, sin_codigo, vacios


def verificar_anonimato(filas):
    """Red de seguridad: aborta si alguna fila trae un campo identificable."""
    for f in filas:
        filtrados = CAMPOS_PROHIBIDOS & set(f.keys())
        if filtrados:
            sys.exit(f"ERROR de anonimización: el CSV contendría {sorted(filtrados)}. Abortado.")


def escribir_csv(filas, codigo):
    ruta = os.path.join(SALIDA_DIR, f"ensayos_{codigo}.csv")
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)
    return ruta


def a_float(txt):
    """Convierte a número tolerando coma decimal. Devuelve None si no es numérico."""
    try:
        return float(txt.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def diagnostico_magnitud(filas):
    """
    Detecta candidatos a error de unidad SIN corregir nada.

    Criterio: un resultado que se aparta de la mediana del analito por un factor
    >= 3 rara vez es dispersión analítica; casi siempre es otra unidad
    (mg/L vs mg/dL = 10x, U/L reportado como mg/dL, etc.).
    """
    por_analito = defaultdict(list)
    for f in filas:
        if f["categoria"].startswith("Quím"):
            v = a_float(f["resultado_raw"])
            if v is not None and v > 0:
                por_analito[f["analito"]].append((f["cod_anonimo"], v, f["unidad_raw"]))

    print("\n" + "=" * 78)
    print("  DIAGNÓSTICO DE MAGNITUD — Química Clínica")
    print("  Candidatos a error de unidad (factor >= 3x respecto a la mediana)")
    print("=" * 78)

    total_sosp = 0
    limpios = []
    for analito in sorted(por_analito):
        datos = por_analito[analito]
        med = statistics.median([v for _, v, _ in datos])
        if med <= 0:
            continue
        sosp = [(c, v, u) for c, v, u in datos if v / med >= 3 or med / v >= 3]
        if not sosp:
            limpios.append(analito)
            continue
        total_sosp += len(sosp)
        print(f"\n  {analito}  (n={len(datos)}, mediana={med:g})")
        for cod, v, u in sorted(sosp, key=lambda x: -x[1]):
            factor = v / med if v > med else -(med / v)
            print(f"      {cod:<6}{v:>12g} {u:<10}  {factor:+.0f}x")

    if limpios:
        print(f"\n  Sin candidatos ({len(limpios)}): {', '.join(limpios)}")
    print("\n" + "-" * 78)
    print(f"  Total de valores sospechosos: {total_sosp}")
    print("-" * 78)
    return total_sosp


def main():
    ap = argparse.ArgumentParser(description="Extrae resultados de una ronda desde Firestore a CSV.")
    ap.add_argument("--codigo", help="Código de ensayo (por defecto: la ronda activa de config.json)")
    args = ap.parse_args()

    codigo = args.codigo or ronda_activa()["codigo"]
    print(f"Extrayendo resultados de {codigo} …")

    db = conectar()
    filas, sin_codigo, vacios = extraer(db, codigo)

    if not filas:
        sys.exit(f"No se encontraron resultados para {codigo}.")

    verificar_anonimato(filas)
    ruta = escribir_csv(filas, codigo)

    labs = len({f["cod_anonimo"] for f in filas})
    quim = sum(1 for f in filas if f["categoria"].startswith("Quím"))
    uro  = sum(1 for f in filas if f["categoria"].startswith("Uro"))

    print(f"\n  Laboratorios:        {labs}")
    print(f"  Filas Química:       {quim}")
    print(f"  Filas Uroanálisis:   {uro}")
    print(f"  Celdas vacías omitidas: {vacios}")
    if sin_codigo:
        print(f"  ATENCIÓN: {sin_codigo} documento(s) sin cod_anonimo, excluidos.")
    print(f"\n  CSV escrito en: {ruta}")

    diagnostico_magnitud(filas)


if __name__ == "__main__":
    main()
