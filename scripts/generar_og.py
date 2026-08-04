"""
Genera las imágenes de vista previa (Open Graph) del sitio.

Salida: assets/images/og/<nombre>.jpg — 1200x630, que es el formato que piden
Facebook, LinkedIn, WhatsApp y X.

Por qué se generan y se COMMITEAN como imagen estática: los rastreadores de
redes sociales no ejecutan JavaScript ni esperan a un fetch. Una tarjeta que se
dibujara en el navegador quedaría en blanco en la vista previa.

QUÉ NO DEBE IR EN LA TARJETA
----------------------------
Las cifras de desempeño de la ronda (% de no conformes, laboratorios
satisfactorios) NO se incluyen a propósito. La imagen circula sola, separada
de la metodología, y un porcentaje de no conformidad fuera de contexto se lee
como un juicio sobre los laboratorios participantes. Solo van datos neutros:
código, área, número de participantes, número de analitos y fecha.

El sitio se sirve en https://www.concalabuasd.com (CNAME del repo, GitHub Pages);
las etiquetas og:image de las páginas apuntan ahí, no a raw.githubusercontent ni al
dominio de Firebase, que no está activo.

Uso:
  conda activate concalab
  python scripts/generar_og.py                    # todas
  python scripts/generar_og.py --codigo EA-001-2026
"""

import os
import re
import sys
import json
import glob
import shutil
import argparse
import subprocess
import tempfile
from datetime import date

RAIZ        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA_DIR  = os.path.join(RAIZ, "assets", "images", "og")
CONFIG_PATH = os.path.join(RAIZ, "data", "config.json")
LOGO        = os.path.join(RAIZ, "assets", "images", "logo-concalab.png")

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

AREAS = {"quimica": "Química Clínica", "uroanalisis": "Uroanálisis"}


def navegador():
    for c in ("google-chrome", "chromium", "chromium-browser"):
        if shutil.which(c):
            return c
    sys.exit("ERROR: no se encontró Chrome/Chromium para renderizar las tarjetas.")


def plantilla(eyebrow, titulo, subtitulo, stats, badges, logo_uri):
    """
    Tarjeta 1200x630 con la identidad del sitio: azul UASD, filete dorado,
    Playfair Display en el titular e IBM Plex Sans en el resto.
    """
    filas = "".join(
        f'<div class="stat"><div class="n">{v}</div><div class="k">{k}</div></div>'
        for v, k in stats
    )
    chips = "".join(f'<span class="chip">{b}</span>' for b in badges)

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ width:1200px; height:630px; overflow:hidden;
         font-family:'IBM Plex Sans',sans-serif;
         background:#003f87;
         background-image:
           radial-gradient(circle at 82% 22%, rgba(253,185,19,.16), transparent 45%),
           linear-gradient(135deg,#00305f 0%,#003f87 55%,#004a9e 100%);
         color:#fff; position:relative; }}
  /* Trama de puntos: da textura sin competir con el texto. */
  body::before {{ content:''; position:absolute; inset:0;
         background-image:radial-gradient(rgba(255,255,255,.07) 1.5px, transparent 1.5px);
         background-size:26px 26px; }}
  .marco {{ position:absolute; inset:0; border-bottom:10px solid #fdb913; }}
  .contenido {{ position:relative; padding:64px 72px; height:100%;
         display:flex; flex-direction:column; }}
  .eyebrow {{ font-size:19px; font-weight:600; letter-spacing:.14em;
         text-transform:uppercase; color:#fdb913; display:flex;
         align-items:center; gap:12px; }}
  .eyebrow::before {{ content:''; width:11px; height:11px; border-radius:50%;
         background:#fdb913; }}
  h1 {{ font-family:'Playfair Display',serif; font-size:88px; line-height:1;
         margin-top:26px; letter-spacing:-.01em; }}
  .regla {{ width:120px; height:5px; background:#fdb913; margin:22px 0 20px; }}
  .sub {{ font-size:31px; font-weight:400; color:#dce8f7; }}
  .stats {{ display:flex; gap:64px; margin-top:auto; }}
  .stat .n {{ font-family:'Playfair Display',serif; font-size:52px; line-height:1; }}
  .stat .k {{ font-size:17px; color:#b9d0ea; margin-top:6px;
         text-transform:uppercase; letter-spacing:.08em; }}
  .pie {{ display:flex; align-items:flex-end; justify-content:space-between;
         margin-top:34px; }}
  .chips {{ display:flex; gap:12px; }}
  .chip {{ font-size:16px; font-weight:600; color:#dce8f7;
         border:1.5px solid rgba(253,185,19,.55); border-radius:6px;
         padding:8px 15px; }}
  /* El PNG del sello es RGB sin transparencia y trae fondo blanco. El sello es
     circular y llena el cuadro, así que recortarlo en círculo elimina las
     esquinas blancas sin tocar el archivo original. */
  .sello {{ width:118px; height:118px; border-radius:50%;
         box-shadow:0 0 0 3px rgba(253,185,19,.5); }}
</style></head>
<body>
  <div class="marco"></div>
  <div class="contenido">
    <div class="eyebrow">{eyebrow}</div>
    <h1>{titulo}</h1>
    <div class="regla"></div>
    <div class="sub">{subtitulo}</div>
    <div class="stats">{filas}</div>
    <div class="pie">
      <div class="chips">{chips}</div>
      <img class="sello" src="{logo_uri}" alt="">
    </div>
  </div>
</body></html>"""


def render(html, destino, navegador_bin):
    """Renderiza la plantilla a JPG de 1200x630."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta_html = os.path.join(tmp, "card.html")
        ruta_png = os.path.join(tmp, "card.png")
        with open(ruta_html, "w", encoding="utf-8") as f:
            f.write(html)

        subprocess.run([
            navegador_bin, "--headless", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars", "--window-size=1200,630",
            # Margen de tiempo para que lleguen las fuentes de Google; sin ellas
            # la tarjeta se dibujaría con la fuente de reserva.
            "--virtual-time-budget=12000",
            f"--screenshot={ruta_png}", f"file://{ruta_html}",
        ], check=True, capture_output=True)

        from PIL import Image
        im = Image.open(ruta_png).convert("RGB")
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        im.save(destino, "JPEG", quality=88, optimize=True)
    return destino


def logo_data_uri():
    """El logo va embebido: el render es file:// y no resolvería una ruta del sitio."""
    import base64
    with open(LOGO, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def datos_ronda(codigo):
    """
    Datos NEUTROS de la ronda. Deliberadamente no devuelve conteos A/C/I:
    ver la nota del encabezado sobre qué no debe ir en la tarjeta.
    """
    candidatos = [
        os.path.join(RAIZ, "data", "informes", f"{codigo}-quimica-clia.json"),
        os.path.join(RAIZ, "data", "informes", f"{codigo}-quimica.json"),
        os.path.join(RAIZ, "data", "informes", f"{codigo}.json"),
    ]
    ruta = next((r for r in candidatos if os.path.exists(r)), None)
    if not ruta:
        return None

    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)

    labs = (d.get("resumen") or {}).get("laboratorios")
    if not labs:
        labs = len({l.get("id") for a in d.get("analitos", [])
                    for l in a.get("laboratorios", [])})

    # Mes de la ronda: se toma del cierre declarado en config cuando el código
    # coincide; si no, se usa el año del propio código, que siempre es cierto.
    etiqueta_fecha = codigo.split("-")[-1]
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            ronda = json.load(f).get("ronda_activa", {})
        if ronda.get("codigo") == codigo and ronda.get("fecha_cierre"):
            y, m, _ = ronda["fecha_cierre"].split("-")
            etiqueta_fecha = f"{MESES[int(m)]} {y}"
    except (OSError, ValueError, KeyError, IndexError):
        pass

    return {
        "labs": labs,
        "analitos": len(d.get("analitos", [])),
        "fecha": etiqueta_fecha,
        "area": AREAS.get(d.get("area", "quimica"), "Química Clínica"),
        "modelo": d.get("modelo"),
    }


def tarjeta_ronda(codigo, logo_uri, navegador_bin):
    info = datos_ronda(codigo)
    if not info:
        print(f"  · {codigo}: sin JSON de informe, omitido")
        return None

    badges = ["ISO 13528:2022"]
    badges.append("CLIA §493.931" if info["modelo"] == "clia" else "ISO/IEC 17043")

    html = plantilla(
        eyebrow="CONCALAB-UASD · Ensayo de Aptitud",
        titulo=codigo,
        subtitulo=f"{info['area']} — Informe de Resultados",
        stats=[(info["labs"], "laboratorios"),
               (info["analitos"], "analitos"),
               (info["fecha"], "ronda")],
        badges=badges,
        logo_uri=logo_uri,
    )
    destino = os.path.join(SALIDA_DIR, f"{codigo}.jpg")
    render(html, destino, navegador_bin)
    print(f"  · {codigo}  →  {os.path.relpath(destino, RAIZ)}")
    return destino


def tarjeta_generica(logo_uri, navegador_bin):
    html = plantilla(
        eyebrow="Universidad Autónoma de Santo Domingo",
        titulo="CONCALAB-UASD",
        subtitulo="Control de Calidad de Laboratorios Clínicos",
        stats=[("Ensayos", "de aptitud"),
               ("Formación", "continua"),
               ("Asesoría", "técnica")],
        badges=["ISO 13528:2022", "ISO/IEC 17043"],
        logo_uri=logo_uri,
    )
    destino = os.path.join(SALIDA_DIR, "concalab.jpg")
    render(html, destino, navegador_bin)
    print(f"  · genérica     →  {os.path.relpath(destino, RAIZ)}")
    return destino


def rondas_disponibles():
    codigos = set()
    for r in glob.glob(os.path.join(RAIZ, "data", "informes", "*.json")):
        m = re.match(r"(EA-\d+-\d{4})", os.path.basename(r))
        if m:
            codigos.add(m.group(1))
    return sorted(codigos)


def main():
    ap = argparse.ArgumentParser(description="Genera las tarjetas Open Graph del sitio.")
    ap.add_argument("--codigo", help="Solo esta ronda (por defecto: todas + la genérica)")
    args = ap.parse_args()

    nav = navegador()
    logo_uri = logo_data_uri()
    print("Generando tarjetas de vista previa (1200x630) …")

    if args.codigo:
        tarjeta_ronda(args.codigo, logo_uri, nav)
    else:
        for codigo in rondas_disponibles():
            tarjeta_ronda(codigo, logo_uri, nav)
        tarjeta_generica(logo_uri, nav)

    print("\n  Recordatorio: las tarjetas son estáticas y se commitean. Si cambia el "
          "número de\n  participantes o de analitos de una ronda, hay que regenerarlas.")


if __name__ == "__main__":
    main()
