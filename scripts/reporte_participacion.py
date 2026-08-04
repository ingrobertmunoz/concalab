"""
Reporte de participación de la ronda activa (uso interno CONCALAB).

Lee la ronda activa desde data/config.json y consulta Firestore
(colección 'resultados_generales') para listar qué laboratorios han
reportado y cuántos analitos lleva cada uno, con desglose por categoría.

Salida:
  1. Tabla en consola.
  2. HTML interno en support/participacion_<codigo>.html
     (lleva nombres reales → NO se commitea; ver .gitignore).

Requisitos:
  conda activate concalab
  pip install firebase-admin

Uso:
  python scripts/reporte_participacion.py
"""

import os
import sys
import json
import html
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore

CREDS_PATH  = "support/concalab-uasd-64ff4-firebase-adminsdk-fbsvc-c400cdf10b.json"
CONFIG_PATH = "data/config.json"
COLECCION   = "resultados_generales"


def ronda_activa():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)["ronda_activa"]


def contar_categorias(resultados):
    """Devuelve (n_quimica, n_uro, total) a partir del array resultados[]."""
    quimica = sum(1 for r in resultados if str(r.get("categoria", "")).startswith("Química"))
    uro     = sum(1 for r in resultados if str(r.get("categoria", "")).startswith("Uro"))
    return quimica, uro, len(resultados)


def obtener_participacion(db, codigo):
    docs = db.collection(COLECCION).where("codigo_ensayo", "==", codigo).stream()
    filas = []
    for d in docs:
        x = d.to_dict()
        q, u, total = contar_categorias(x.get("resultados", []) or [])
        filas.append({
            "laboratorio": x.get("laboratorio", "(sin nombre)"),
            "fecha":       x.get("fecha_reporte", ""),
            "quimica":     q,
            "uro":         u,
            "total":       total,
        })
    # Orden por nombre del laboratorio. Esta tabla NO debe llevar el identificador
    # público del informe, sea cual sea el campo que la ronda declare (cod_anonimo
    # hasta 2025, cod_interno desde EA-001-2026): se difunde con nombres reales, y
    # asociar nombre ↔ identificador de-anonimizaría los informes publicados.
    filas.sort(key=lambda r: r["laboratorio"].lower())
    return filas


def imprimir_consola(ronda, filas):
    print("=" * 78)
    print(f"  PARTICIPACIÓN — {ronda['codigo']} | {ronda.get('descripcion', '')}")
    print(f"  Habilitada: {'SÍ' if ronda.get('habilitado') else 'NO'} | "
          f"Laboratorios que han reportado: {len(filas)}")
    print("=" * 78)
    if not filas:
        print("  Aún no hay reportes para esta ronda.")
        print("=" * 78)
        return
    print(f"  {'Laboratorio':<48}{'Fecha':<12}{'Quím':>5}{'Uro':>5}{'Tot':>5}")
    print("  " + "-" * 74)
    for r in filas:
        nombre = (r["laboratorio"][:45] + "…") if len(r["laboratorio"]) > 46 else r["laboratorio"]
        print(f"  {nombre:<48}{r['fecha']:<12}"
              f"{r['quimica']:>5}{r['uro']:>5}{r['total']:>5}")
    print("=" * 78)


def escribir_html(ronda, filas):
    generado = datetime.now().strftime("%d/%m/%Y %H:%M")
    AZUL, DORADO = "#003f87", "#fdb913"

    filas_html = ""
    for i, r in enumerate(filas):
        bg = "#ffffff" if i % 2 == 0 else "#f4f6fb"
        filas_html += (
            f'<tr style="background:{bg};">'
            f'<td>{html.escape(r["laboratorio"])}</td>'
            f'<td style="text-align:center;">{html.escape(r["fecha"])}</td>'
            f'<td style="text-align:center;">{r["quimica"]}</td>'
            f'<td style="text-align:center;">{r["uro"]}</td>'
            f'<td style="text-align:center;font-weight:700;">{r["total"]}</td>'
            f"</tr>\n"
        )
    if not filas:
        filas_html = ('<tr><td colspan="5" style="text-align:center;padding:1.5rem;color:#888;">'
                      "Aún no hay reportes para esta ronda.</td></tr>")

    doc = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Participación {html.escape(ronda['codigo'])} — CONCALAB (interno)</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color:#222; margin:2rem; background:#fafbfe; }}
  .aviso {{ background:#fff3cd; border-left:4px solid {DORADO}; padding:.6rem 1rem; font-size:.85rem;
           border-radius:4px; margin-bottom:1.2rem; }}
  h1 {{ color:{AZUL}; font-size:1.4rem; margin-bottom:.2rem; }}
  .sub {{ color:#555; margin-bottom:1.2rem; font-size:.95rem; }}
  table {{ border-collapse:collapse; width:100%; max-width:900px; box-shadow:0 2px 10px rgba(0,0,0,.08); }}
  th, td {{ border:1px solid #d9deea; padding:.55rem .7rem; font-size:.9rem; }}
  th {{ background:{AZUL}; color:#fff; text-align:center; }}
  caption {{ caption-side:bottom; color:#888; font-size:.8rem; padding-top:.6rem; text-align:left; }}
</style></head><body>
<div class="aviso">Tabla de difusión a los participantes. Sin el identificador público del informe (no debe asociarse nombre ↔ identificador). No publicar en el sitio web ni commitear.</div>
<h1>Participación — {html.escape(ronda['codigo'])}</h1>
<div class="sub">{html.escape(ronda.get('descripcion',''))} ·
  Ronda {'habilitada' if ronda.get('habilitado') else 'cerrada'} ·
  <strong>{len(filas)}</strong> laboratorio(s) han reportado</div>
<table>
  <thead><tr>
    <th>Laboratorio</th><th>Fecha de<br>reporte</th>
    <th>Química</th><th>Uroanálisis</th><th>Total</th>
  </tr></thead>
  <tbody>
{filas_html}  </tbody>
  <caption>Generado el {generado} · Fuente: Firestore «{COLECCION}»</caption>
</table>
</body></html>"""

    ruta = f"support/participacion_{ronda['codigo']}.html"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(doc)
    return ruta


def main():
    if not os.path.exists(CREDS_PATH):
        print(f"\n  ERROR: no se encontró la clave de servicio: {CREDS_PATH}\n")
        sys.exit(1)

    ronda = ronda_activa()
    firebase_admin.initialize_app(credentials.Certificate(CREDS_PATH))
    db = firestore.client()

    filas = obtener_participacion(db, ronda["codigo"])
    imprimir_consola(ronda, filas)
    ruta = escribir_html(ronda, filas)
    print(f"\n  ✓ HTML interno generado: {ruta}")
    print("    (lleva nombres reales — no lo subas al repositorio)")


if __name__ == "__main__":
    main()
