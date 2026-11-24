"""
Conferencia en el XXII Congreso Nacional de Profesionales del Laboratorio
Clínico (CODOBIO, 26 de noviembre de 2026) — CONCALAB-UASD.

Qué es
------
«Situación actual de los resultados de Química Clínica en la República
Dominicana». Es la tercera presentación del proyecto y la única para un
público abierto: ni la devolución a los participantes (`presentacion.py`) ni
la ejecutiva al Decanato (`presentacion_ejecutiva.py`). En la sala habrá
participantes de la ronda, así que cada cifra fuerte lleva su contexto en la
MISMA lámina (criterio, 37 voluntarios, una ronda): en un congreso las
láminas se fotografían y circulan solas, por la misma razón por la que la
tarjeta OG no lleva cifras de desempeño.

Por qué PowerPoint y no reveal.js
---------------------------------
Las normas del congreso exigen PowerPoint 16:9 y prohíben conectar equipos
propios. Se genera con python-pptx SOBRE LA PLANTILLA DEL CONGRESO (su
encabezado y su franja), no se convierte desde HTML: lo que sale de una
conversión queda peor que lo que se compone directamente.

De dónde salen las cifras
-------------------------
Del mismo `data/informes/<codigo>-quimica-clia.json` que leen la web, el PDF,
la tarjeta OG y las otras dos presentaciones, y de `paper/generado/macros.tex`
para lo que solo existe en el artículo (denominador nacional). Ninguna se
teclea a mano. Lo único escrito aquí son los umbrales clínicos del potasio,
con su fuente citada en la propia lámina.

Estructura: el lema del congreso en tres actos
----------------------------------------------
«Más allá del dato, la vida»  → Kelvin, el laboratorio como sistema de
                                 medida y el caso del potasio.
El dato                        → la situación actual (resultados, Decreto
                                 350-04, cobertura).
«Modelando el mañana… con      → la IA hereda el dato, la compuerta humana y
 sentido humano»                 qué hacer.

Uso:
  conda activate concalab
  python scripts/presentacion_congreso.py
  python scripts/presentacion_congreso.py --pdf     # además, vista previa PDF

Salida en congreso/<carpeta con el nombre que exige el congreso>/, que está
en .gitignore: la presentación se publica en el portal después de revisarla.
"""

import re
import copy
import shutil
import argparse
import subprocess
from pathlib import Path

import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import qrcode
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "congreso" / "3.-Plantilla_Presentaciones_Congreso_2026.pptx"
# Nombre que exigen las normas: día, hora, salón y primer expositor.
CARPETA = RAIZ / "congreso" / "26Nov2026_04-20pm_Salon_Pitiusa_RobertMunoz"
ARCHIVO = "Situacion_Quimica_Clinica_RD_CONCALAB-UASD.pptx"
FIGS = RAIZ / "congreso" / "_figs"
# PDF que se publica en el portal educativo (solo láminas: las notas del orador
# NO van, porque llevan indicaciones internas). No va en publicaciones/
# presentaciones/, que está excluida a propósito del despliegue. El repositorio
# ignora *.pdf: este archivo se agregó con `git add -f` y desde entonces se sigue.
PDF_PORTAL = RAIZ / "publicaciones" / "congresos" / "CODOBIO-2026-situacion-quimica-clinica.pdf"

URL_PORTAL = "https://www.concalabuasd.com/portal-educativo.html#congreso-2026"
URL_PORTAL_CORTA = "concalabuasd.com  ›  Educación"
URL_ARTICULO = ("https://www.researchgate.net/publication/415301255_Analytical_"
                "performance_in_clinical_chemistry_an_observational_study_of_37_"
                "Dominican_clinical_laboratories_against_international_total_"
                "allowable_error_specifications")

# El título del programa del congreso, sin tocar —el público debe reconocer la
# charla que eligió— más una precisión que lo acota a los participantes: el
# título solo no distingue 37 laboratorios del país entero. El número sale del
# JSON, como en el título del artículo.
TITULO = ("Situación actual de los resultados de Química Clínica "
          "en la República Dominicana")
PRECISION = "Ensayo de aptitud: {n} laboratorios participantes"
# Analito de la lámina «De cerca». Glucosa y no potasio: es el más conocido, el
# de más peso en la mortalidad del país (diabetes, tercera causa de muerte; ver
# el artículo) y su % dentro del criterio es casi el de la ronda entera, así que
# no es un caso elegido a conveniencia. Usa la misma escala relativa que los
# extremos (EXTREMOS_ESCALA): las tres láminas se comparan entre sí. Lo que se
# sale del eje se dibuja como triángulo en el borde, no se oculta.
EJEMPLO = "Glucosa"
EJEMPLO_PASO = 5

# Lámina «Los extremos»: un analito de los más bajos y uno de los más altos.
# El alto es ALT y NO bilirrubina directa, aunque esta tenga el % más alto: CLIA
# no la regula y su límite (EFLM) es ±44,5 %, frente a 8–20 % de los analitos
# de CLIA, y su CV es el mayor de la ronda. Su «éxito» es del criterio, no de
# los laboratorios; presentarla como el mejor caso diría lo contrario de lo que
# pasó. Ambos paneles usan la misma escala relativa (±EXTREMOS_ESCALA de X*).
EXTREMOS = ("Colesterol HDL", "ALT (TGP)")
EXTREMOS_ESCALA = 0.6

EXPOSITOR = "Mtro. Robert Muñoz Rivera"
CARGO = "Científico de datos · CONCALAB-UASD"
AUTORES = [
    "Mariolga Roques Ortiz", "Magdalena Yvelisse Villar Diroche",
    "Leonardo Andrés Rosario", 
    "Robert Antonio Muñoz Rivera",
]

# ── Paleta ────────────────────────────────────────────────────────────────
# El cromo es el de la plantilla del congreso; el semáforo de estado es el del
# proyecto (css/main.css), y siempre va acompañado de su etiqueta.
NAVY = "0B3954"
CIAN = "00C6D8"
NARANJA = "E07E00"
TINTA = "1F2A33"
GRIS_TXT = "484F55"
GRIS_CLARO = "C2CDD2"
VERDE, AMARILLO, ROJO = "#28a745", "#e0a800", "#dc3545"
FUENTE = "Arial"


def rgb(h):
    return RGBColor.from_string(h.lstrip("#"))


def num(x, dec=1):
    """Punto decimal, como en el artículo y en los reportes de laboratorio
    que escribe este público. Cambiarlo a coma es esta única línea."""
    return f"{x:.{dec}f}"


def leer_macros():
    t = (RAIZ / "paper" / "generado" / "macros.tex").read_text(encoding="utf-8")
    return dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", t))


def buscar(d, nombre):
    return next(a for a in d["analitos"] if a["nombre"] == nombre)


# ── Figuras ───────────────────────────────────────────────────────────────
# Se proyectan en un salón: todo sube de tamaño respecto al PDF. PNG a 220 dpi
# porque python-pptx no inserta SVG; a ese tamaño de lámina no se pixela.

def _estilo():
    from matplotlib import font_manager
    hay = {f.name for f in font_manager.fontManager.ttflist}
    familia = [f for f in ("Arial", "Liberation Sans") if f in hay] or ["DejaVu Sans"]
    plt.rcParams.update({
        "font.family": familia,
        "font.size": 15, "axes.labelsize": 15,
        "xtick.labelsize": 14, "ytick.labelsize": 14,
        "axes.edgecolor": "#8a949c", "axes.labelcolor": "#" + TINTA,
        "xtick.color": "#" + GRIS_TXT, "ytick.color": "#" + GRIS_TXT,
    })


def _limpio(ax, izq=False):
    for lado in ("top", "right") + (("left",) if not izq else ()):
        ax.spines[lado].set_visible(False)


def _guardar(fig, destino):
    fig.savefig(destino, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _apilar(vals, paso):
    """Dot plot apilado: cada valor sube un escalón por cada vecino que ya
    ocupa su casilla. Muestra la distribución sin ocultar a nadie."""
    ocup, ys = {}, []
    for v in vals:
        k = round(v / paso)
        ys.append(ocup.get(k, 0))
        ocup[k] = ocup.get(k, 0) + 1
    return np.array(ys)


COLOR_CLASE = {"A": VERDE, "C": AMARILLO, "I": ROJO}
NOMBRE_CLASE = {"A": "Satisfactorio", "C": "Alerta", "I": "No satisfactorio"}


def fig_tira(a, destino, paso, xlim, zonas=(), unidad="", tam=(10.4, 3.7),
             leyenda=True):
    """Los resultados de todos los laboratorios para un mismo suero, sobre el
    eje de la magnitud. `zonas` son bandas clínicas de fondo (x0, x1, rótulo)."""
    labs = sorted((l for l in a["laboratorios"] if l.get("resultado") is not None),
                  key=lambda l: l["resultado"])
    xs = np.array([l["resultado"] for l in labs])
    ys = _apilar(xs, paso)
    xa, de = a["valor_asignado"], a["eta"]["delta_e"]
    techo = ys.max() + 1

    fig, ax = plt.subplots(figsize=tam)
    tonos = ["#f2f4f5", "#e4e8eb"]
    for i, (x0, x1, txt) in enumerate(zonas):
        ax.axvspan(x0, x1, color=tonos[i % 2], zorder=0, lw=0)
        ax.annotate(txt, xy=((max(x0, xlim[0]) + min(x1, xlim[1])) / 2, techo + 1.55),
                    ha="center", va="center", fontsize=13, color="#" + GRIS_TXT,
                    annotation_clip=False)
    ax.axvspan(xa - de, xa + de, color="#" + CIAN, alpha=0.22, zorder=1, lw=0)
    ax.axvline(xa, color="#" + NAVY, lw=2, ls="--", zorder=2)
    dec = 2 if xa < 20 else 1        # mismas cifras que el subtítulo de la lámina
    ax.annotate(f"Valor asignado {num(xa, dec)} {unidad}\n(banda: límite CLIA ±{num(de, dec)})",
                xy=(xa, techo + 0.25), ha="center", va="bottom", fontsize=13,
                color="#" + NAVY, fontweight="bold", annotation_clip=False)
    dentro_eje = (xs >= xlim[0]) & (xs <= xlim[1])
    for clase in ("A", "C", "I"):
        m = np.array([l["clasificacion"] == clase for l in labs]) & dentro_eje
        if m.any():
            ax.scatter(xs[m], ys[m] + 0.5, s=170, color=COLOR_CLASE[clase],
                       edgecolor="white", linewidth=1.6, zorder=3,
                       label=NOMBRE_CLASE[clase])
    # Regla del informe web: un extremo no estira el eje ni se oculta. Se dibuja
    # como triángulo en el borde hacia el que se sale, con su valor escrito.
    rango = xlim[1] - xlim[0]
    fuera = {True: 0, False: 0}      # cuántos van ya en cada borde, para apilar
    for x, l in zip(xs, labs):
        if x < xlim[0] or x > xlim[1]:
            izq = x < xlim[0]
            nivel = fuera[izq]
            fuera[izq] += 1
            bx = xlim[0] + rango * 0.012 if izq else xlim[1] - rango * 0.012
            ax.scatter([bx], [0.5 + nivel], marker="<" if izq else ">", s=260, zorder=4,
                       color=COLOR_CLASE[l["clasificacion"]], edgecolor="white",
                       linewidth=1.4)
            ax.annotate(f"{x:g}", xy=(bx, 1.25 + nivel), ha="left" if izq else "right",
                        fontsize=13, color="#" + GRIS_TXT, fontweight="bold")
    ax.set_xlim(*xlim)
    ax.set_ylim(0, techo + 0.2)
    ax.set_yticks([])
    ax.set_xlabel(f"Resultado informado ({unidad})")
    _limpio(ax)
    if leyenda:
        ax.legend(loc="upper left", ncol=1, frameon=True, framealpha=0.92,
                  edgecolor="white", fontsize=13, handletextpad=0.3,
                  title="Según CLIA", title_fontsize=13, alignment="left")
    _guardar(fig, destino)


def fig_diana(destino):
    """Precisión frente a exactitud. El mismo grupo de puntos, visto con y sin
    el centro verdadero: es todo lo que el control interno no puede ver."""
    rng = np.random.default_rng(7)
    pts = rng.normal(0, 0.10, size=(14, 2)) + np.array([0.55, 0.34])
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
    for i, ax in enumerate(axs):
        if i == 1:
            for r, c in [(1.0, "#e9eef1"), (0.66, "#d3dde3"), (0.33, "#b9c8d1")]:
                ax.add_patch(plt.Circle((0, 0), r, color=c, zorder=0))
            ax.plot(0, 0, marker="+", ms=26, mew=3, color="#" + NAVY, zorder=2)
            ax.annotate("", xy=(0.45, 0.27), xytext=(0.05, 0.03),
                        arrowprops=dict(arrowstyle="-|>", lw=2.6, color=ROJO,
                                        mutation_scale=22))
            ax.annotate("sesgo", xy=(0.30, -0.02), fontsize=18, color=ROJO,
                        fontweight="bold", ha="left", va="top")
        ax.scatter(pts[:, 0], pts[:, 1], s=130, color="#" + NAVY, zorder=3,
                   edgecolor="white", linewidth=1)
        ax.set_xlim(-1.08, 1.08)
        ax.set_ylim(-1.08, 1.08)
        ax.set_aspect("equal")
        ax.axis("off")
    axs[0].set_title("Lo que ve el control interno:\nlos resultados se repiten",
                     fontsize=16, color="#" + TINTA, pad=10)
    axs[1].set_title("Lo que ve el ensayo de aptitud:\nel valor correcto estaba en otro lugar",
                     fontsize=16, color="#" + TINTA, pad=10)
    _guardar(fig, destino)


def fig_criterio(destino):
    """La regla de decisión dibujada: |z| = 3 ES el límite de CLIA."""
    fig, ax = plt.subplots(figsize=(11.6, 2.0))
    tramos = [(-6, -3, ROJO), (-3, -2, AMARILLO), (-2, 2, VERDE),
              (2, 3, AMARILLO), (3, 6, ROJO)]
    for x0, x1, c in tramos:
        ax.axvspan(x0 + 0.03, x1 - 0.03, color=c, alpha=0.85, lw=0)
    for x, txt in [(-3, "−ETa"), (3, "+ETa"), (0, "Valor asignado")]:
        ax.axvline(x, color="#222", lw=1.6, ls="--" if x else "-")
        ax.annotate(txt, xy=(x, 1.08), ha="center", fontsize=15,
                    fontweight="bold", color="#222", annotation_clip=False)
    for x, txt, c in [(0, "Satisfactorio\n|z| ≤ 2", "#fff"), (2.5, "Alerta", "#1c2430"),
                      (-2.5, "Alerta", "#1c2430"), (4.5, "No satisfactorio", "#fff"),
                      (-4.5, "No satisfactorio", "#fff")]:
        ax.annotate(txt, xy=(x, 0.5), ha="center", va="center", fontsize=15,
                    fontweight="bold", color=c)
    ax.set_xlim(-6, 6)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xticks([-6, -3, -2, 0, 2, 3, 6])
    ax.set_xlabel("Z-Score   (σpt = ETa / 3)")
    _limpio(ax)
    _guardar(fig, destino)


def fig_resultados(d, destino):
    """Una sola barra al 100 %: la proporción se lee de un vistazo."""
    r = d["resumen"]
    partes = [(r["aceptables"], "Satisfactorio", VERDE, "white"),
              (r["cuestionables"], "Alerta", AMARILLO, "#1c2430"),
              (r["inaceptables"], "No satisfactorio", ROJO, "white")]
    fig, ax = plt.subplots(figsize=(11.6, 2.0))
    x = 0
    for n, txt, c, tc in partes:
        p = n / r["total"] * 100
        ax.barh(0, p - 0.25, left=x, color=c, height=0.8)
        ax.annotate(f"{num(p)} %", xy=(x + p / 2, 0.08), ha="center", va="center",
                    fontsize=22, fontweight="bold", color=tc)
        ax.annotate(f"{txt} ({n})", xy=(x + p / 2, -0.24), ha="center",
                    va="center", fontsize=13, color=tc)
        x += p
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.45, 0.45)
    ax.axis("off")
    _guardar(fig, destino)


def fig_estratos(d, destino):
    est = d["desempeno_global"]["estratos"]
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    ys = np.arange(len(est))[::-1]
    ax.barh(ys, [e["laboratorios"] for e in est],
            color=[e["color"] for e in est], height=0.62)
    for y, e in zip(ys, est):
        ax.annotate(f"  {e['laboratorios']} lab. ({num(e['pct'])} %)",
                    xy=(e["laboratorios"], y), va="center", fontsize=16,
                    fontweight="bold", color="#" + TINTA)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{e['nombre']}\n{e['descripcion']}" for e in est],
                       fontsize=14)
    ax.set_xlim(0, d["desempeno_global"]["laboratorios"] * 1.3)
    ax.set_xticks([])
    _limpio(ax)
    ax.spines["bottom"].set_visible(False)
    _guardar(fig, destino)


def fig_distribucion(d, mediana, destino):
    """Panel (a) de la figura 1 del artículo, redibujado para proyectar:
    laboratorios por número de resultados no satisfactorios, con el color de su
    estrato. El panel (b) —la curva de concentración— no se usa en la sala: no
    se lee en segundos y su lectura rápida («la curva se separa») empuja a la
    conclusión contraria a la de la lámina. Conteos: `por_laboratorio[].I`."""
    g = d["desempeno_global"]
    est = g["estratos"]

    def estrato(n):
        return next(e for e in est
                    if n >= e["desde"] and (e["hasta"] is None or n <= e["hasta"]))

    conteo = {}
    for lab in g["por_laboratorio"]:
        conteo[lab["I"]] = conteo.get(lab["I"], 0) + 1
    xs = sorted(conteo)
    fig, ax = plt.subplots(figsize=(8.6, 4.3))
    ax.bar(xs, [conteo[x] for x in xs], width=0.8,
           color=[estrato(x)["color"] for x in xs])
    ax.axvline(mediana, color="#" + NAVY, lw=2, ls="--")
    # Sin leyenda dentro del gráfico: tapaba la mediana y la barra más alta.
    # Los estratos se rotulan en el panel derecho de la lámina.
    ax.annotate(f"mediana: {mediana}", xy=(mediana + 0.3, max(conteo.values()) + 0.5),
                fontsize=14, color="#" + NAVY, fontweight="bold")
    ax.set_xlabel("Resultados no satisfactorios por laboratorio")
    ax.set_ylabel("Laboratorios")
    ax.set_xticks(range(0, max(xs) + 1, 2))
    ax.set_ylim(0, max(conteo.values()) + 1.2)
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.grid(axis="y", lw=0.6, color="#dde3e7")
    ax.set_axisbelow(True)
    _limpio(ax, izq=True)
    _guardar(fig, destino)


def fig_analitos(d, destino):
    """% dentro del criterio por analito, de peor a mejor. Un solo tono: es
    magnitud, no estado (CLIA califica resultados, no analitos)."""
    ev = sorted((a for a in d["analitos"] if a["conteos"]["pct_dentro"] is not None),
                key=lambda a: a["conteos"]["pct_dentro"])
    vals = [a["conteos"]["pct_dentro"] for a in ev]
    fig, ax = plt.subplots(figsize=(11.9, 4.35))
    xs = np.arange(len(ev))
    ax.bar(xs, vals, color="#" + NAVY, width=0.72)
    for x, v in zip(xs, vals):
        ax.annotate(f"{v:.0f}", xy=(x, v + 1.2), ha="center", fontsize=11,
                    color="#" + GRIS_TXT)
    ax.set_xticks(xs)
    ax.set_xticklabels([a["nombre"].replace(" (ALT/TGP)", "").replace(" (AST/TGO)", "")
                        for a in ev], rotation=55, ha="right", fontsize=11.5)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("% de resultados\ndentro del criterio")
    ax.grid(axis="y", lw=0.6, color="#dde3e7")
    ax.set_axisbelow(True)
    _limpio(ax, izq=True)
    _guardar(fig, destino)


def qr(url, destino):
    q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M,
                      box_size=12)
    q.add_data(url)
    q.make(fit=True)
    q.make_image(fill_color="#" + NAVY, back_color="white").save(destino)


# ── Maquetación sobre la plantilla ────────────────────────────────────────

class Mazo:
    """La plantilla trae tres láminas: portada, especificaciones y una
    interior vacía con la franja del congreso. La franja es una imagen dentro
    de un marcador; se clona en cada lámina nueva y al final se retiran las
    dos láminas de muestra."""

    def __init__(self, plantilla):
        self.prs = Presentation(plantilla)
        muestra = self.prs.slides[2]
        self.layout = muestra.slide_layout
        # Es un marcador de posición relleno de imagen: shape_type dice
        # PLACEHOLDER, así que se busca por la etiqueta XML <p:pic>.
        pic = next(s for s in muestra.shapes if s._element.tag.endswith("}pic"))
        self.franja = copy.deepcopy(pic._element)
        self.franja_img = muestra.part.related_part(
            pic._element.blipFill.blip.rEmbed)
        self.n = 0

    # — láminas —
    def portada(self):
        return self.prs.slides[0]

    def lamina(self, titulo, subtitulo=None, notas=""):
        s = self.prs.slides.add_slide(self.layout)
        for ph in list(s.placeholders):
            if ph.placeholder_format.type != 1:          # se queda el título
                ph._element.getparent().remove(ph._element)
        el = copy.deepcopy(self.franja)
        cnv = el.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr")
        cnv.set("id", "900")
        for ext in cnv.findall("{http://schemas.openxmlformats.org/drawingml/2006/main}extLst"):
            cnv.remove(ext)
        el.blipFill.blip.rEmbed = s.part.relate_to(self.franja_img, RT.IMAGE)
        s.shapes._spTree.insert(2, el)

        t = s.shapes.title
        t.left, t.top, t.width, t.height = Inches(0.65), Inches(0.28), Inches(12.0), Inches(0.72)
        tf = t.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.BOTTOM
        p = tf.paragraphs[0]
        p.text = titulo
        p.alignment = PP_ALIGN.LEFT
        _fmt(p.runs[0], 32, True, NAVY)
        if subtitulo:
            texto(s, 0.67, 1.0, 12.0, 0.4, [(subtitulo, 18, False, GRIS_TXT)])
        rect(s, 0.67, 1.45, 12.0, 0.035, CIAN)
        self.n += 1
        # pie: dirección del sitio y número, sin tocar la franja del congreso
        texto(s, 8.4, 6.1, 4.3, 0.3, [(f"concalabuasd.com   ·   {self.n + 1}", 11,
                                       False, GRIS_TXT)], alinear=PP_ALIGN.RIGHT)
        if notas:
            s.notes_slide.notes_text_frame.text = notas.strip()
        return s

    def retirar_muestras(self):
        lst = self.prs.slides._sldIdLst
        for sid in list(lst)[1:3]:
            self.prs.part.drop_rel(sid.rId)
            lst.remove(sid)

    def guardar(self, destino):
        self.retirar_muestras()
        # La plantilla del congreso trae como autora a quien la preparó; sin
        # esto, el PDF publicado la mostraría como autora de la presentación.
        cp = self.prs.core_properties
        cp.author = cp.last_modified_by = "CONCALAB-UASD"
        cp.title = TITULO
        cp.subject = "XXII Congreso Nacional de Profesionales del Laboratorio Clínico (CODOBIO)"
        self.prs.save(destino)


def _fmt(run, size, bold=False, color=TINTA, italic=False):
    f = run.font
    f.name = FUENTE
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = rgb(color)


def texto(s, x, y, w, h, parrafos, alinear=PP_ALIGN.LEFT, ancla=MSO_ANCHOR.TOP,
          espacio=6):
    """`parrafos`: lista de (texto, tamaño, negrita, color). Dentro del texto,
    **así** va en negrita."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancla
    tf.margin_left = tf.margin_right = Inches(0.04)
    # Cada «\n» abre un párrafo con el mismo formato: un salto dentro del run
    # rompe la alineación centrada en PowerPoint.
    parrafos = [(linea, size, bold, color) for (t, size, bold, color) in parrafos
                for linea in t.split("\n")]
    for i, (t, size, bold, color) in enumerate(parrafos):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = alinear
        p.space_after = Pt(espacio)
        for j, trozo in enumerate(t.split("**")):
            if not trozo:
                continue
            _fmt(p.add_run(), size, bold or j % 2 == 1, color)
            p.runs[-1].text = trozo
    return tb


def rect(s, x, y, w, h, color, forma=MSO_SHAPE.RECTANGLE, linea=None):
    r = s.shapes.add_shape(forma, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = rgb(color)
    if linea:
        r.line.color.rgb = rgb(linea)
    else:
        r.line.fill.background()
    r.shadow.inherit = False
    return r


def caja(s, x, y, w, h, lineas, fondo, tinta="FFFFFF", size=18):
    r = rect(s, x, y, w, h, fondo, MSO_SHAPE.ROUNDED_RECTANGLE)
    r.adjustments[0] = 0.12
    tf = r.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    # Cada «\n» abre un párrafo: un salto dentro del run descentra la línea.
    # Las líneas que salen de partir la primera conservan su tamaño.
    partes = [(linea, bold, j == 0) for j, (t, bold) in enumerate(lineas)
              for linea in t.split("\n")]
    for i, (t, bold, primera) in enumerate(partes):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        _fmt(p.add_run(), size if primera else size - 4, bold, tinta)
        p.runs[0].text = t
    return r


def imagen(s, ruta, x, y, w=None, h=None):
    return s.shapes.add_picture(str(ruta), Inches(x), Inches(y),
                                Inches(w) if w else None, Inches(h) if h else None)


def fuente(s, t):
    texto(s, 0.67, 5.98, 7.8, 0.45, [(t, 12, False, GRIS_TXT)], espacio=0)


def cifra(s, x, y, w, valor, rotulo, color=NAVY, size=54):
    texto(s, x, y, w, 1.0, [(valor, size, True, color)], alinear=PP_ALIGN.CENTER)
    texto(s, x, y + 1.0, w, 0.9, [(rotulo, 17, False, GRIS_TXT)],
          alinear=PP_ALIGN.CENTER)


# ── Contenido ─────────────────────────────────────────────────────────────

def construir(d, m):
    FIGS.mkdir(parents=True, exist_ok=True)
    _estilo()
    mz = Mazo(PLANTILLA)
    r, g = d["resumen"], d["desempeno_global"]
    codigo = d["codigo"]
    k = buscar(d, EJEMPLO)
    kv = [l["resultado"] for l in k["laboratorios"] if l.get("resultado") is not None]
    pct_no = r["inaceptables"] / r["total"] * 100
    ctx = (f"{codigo} · {r['laboratorios']} laboratorios participantes voluntarios · "
           f"{r['total']} resultados evaluados · criterio CLIA (42 CFR §493.931)")

    qr(URL_PORTAL, FIGS / "qr_portal.png")
    qr(URL_ARTICULO, FIGS / "qr_articulo.png")

    # 1 ─ Portada ───────────────────────────────────────────────────────────
    s = mz.portada()
    for sh in s.placeholders:
        tipo = sh.placeholder_format.type
        tf = sh.text_frame
        if tipo in (1, 3):                                 # título
            sh.left, sh.top, sh.width, sh.height = Inches(1.2), Inches(3.3), Inches(10.9), Inches(1.65)
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.TOP
            for extra in tf.paragraphs[1:]:
                extra._p.getparent().remove(extra._p)
            p = tf.paragraphs[0]
            p.text = TITULO + ":"
            p.alignment = PP_ALIGN.CENTER
            _fmt(p.runs[0], 30, True, NAVY)
            p2 = tf.add_paragraph()
            p2.text = PRECISION.format(n=r["laboratorios"])
            p2.alignment = PP_ALIGN.CENTER
            p2.space_before = Pt(4)
            _fmt(p2.runs[0], 24, True, NARANJA)
        else:                                              # subtítulo
            sh.left, sh.top, sh.width, sh.height = Inches(1.6), Inches(5.1), Inches(8.9), Inches(1.75)
            lineas = [(EXPOSITOR, 22, True, TINTA),
                      (CARGO, 18, True, NAVY),
                      ("Universidad Autónoma de Santo Domingo · República Dominicana", 18, False, GRIS_TXT)]
            for extra in tf.paragraphs[1:]:
                extra._p.getparent().remove(extra._p)
            for i, (t, size, b, c) in enumerate(lineas):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.text = t
                p.alignment = PP_ALIGN.CENTER
                _fmt(p.runs[0], size, b, c)
    imagen(s, FIGS / "qr_portal.png", 11.05, 4.95, h=1.7)
    texto(s, 10.55, 6.62, 2.75, 0.6, [("Siga la presentación", 13, True, NAVY),
                                       (URL_PORTAL_CORTA, 11, False, GRIS_TXT)],
          alinear=PP_ALIGN.CENTER, espacio=0)
    s.notes_slide.notes_text_frame.text = (
        "Mientras el moderador presenta: dejar el QR a la vista. Lleva al portal "
        "educativo de CONCALAB, donde están el informe interactivo y el artículo.\n\n"
        "Presentarse en una línea —científico de datos de CONCALAB— y pasar "
        "directo a «lo que no se mide, no se mejora»: la charla empieza por la "
        "medición, no por los porcentajes.")

    # ═════ ACTO I — «Más allá del dato, la vida» ═══════════════════════════

    # 4 ─ Medir la medición ───────────────────────────────────────────────
    # Dos láminas con la misma composición: la segunda añade el giro. Simula una
    # aparición por pasos sin animaciones, que dependen de la versión de
    # PowerPoint del equipo del congreso. La frase va como principio de la
    # calidad, sin autor: suele atribuirse a Drucker y el Drucker Institute lo
    # niega. Kelvin (1883) queda al pie como origen documentado de la idea.
    def principio(con_giro):
        s = mz.lamina("Medir la medición", notas=(
            """
El giro, despacio:

«Los laboratorios miden todo el día: es su oficio.» [Pausa].
«Pero ¿quién mide la medición del laboratorio? ¿Quién comprueba que el número
que sale del analizador es el correcto?»

Esa pregunta es el hilo de toda la charla.""" if con_giro else """
Presentarse en una línea —científico de datos de CONCALAB— y entrar aquí.

«En calidad lo sabemos: lo que no se mide, no se mejora.» Es una frase que todos
hemos escuchado. Se suele atribuir a Peter Drucker, aunque el propio Drucker
Institute aclaró que él nunca la escribió. La idea viene de Lord Kelvin, en una
conferencia de 1883 (está al pie).

[Avanzar sin pausa larga: la lámina siguiente trae el giro]."""))
        texto(s, 1.2, 1.75, 10.9, 0.5, [("En calidad lo sabemos:", 22, False, GRIS_TXT)])
        texto(s, 1.2, 2.25, 10.9, 1.0, [("Lo que no se mide, no se mejora.", 40, True, NAVY)])
        if con_giro:
            rect(s, 1.2, 3.68, 0.09, 1.2, NARANJA)
            texto(s, 1.55, 3.6, 10.6, 1.9, [
                ("Los laboratorios miden todo el día.", 26, False, TINTA),
                ("Pero ¿quién mide **la medición del laboratorio**?", 30, False, NARANJA),
            ], espacio=10)
        fuente(s, "La idea se remonta a William Thomson, Lord Kelvin: conferencia ante la "
                  "Institution of Civil Engineers, Londres, 3 de mayo de 1883.")

    principio(False)
    principio(True)

    # 4b ─ Objetivo y recorrido ──────────────────────────────────────────
    # La plantilla del congreso sugiere «Portada → Objetivo → Desarrollo…». Va
    # DESPUÉS de «Medir la medición», no antes: la pregunta «¿quién mide la
    # medición?» lleva directo al objetivo. El recorrido son los tres actos del
    # lema, no una lista de secciones. La primera mitad del objetivo es la del
    # artículo; la segunda, lo que el equipo hizo y puede demostrar —un agente
    # de IA que automatiza el procesamiento—, no un terreno médico.
    s = mz.lamina("Objetivo y recorrido", notas=f"""
Esa pregunta —¿quién mide la medición?— es lo que hicimos. El objetivo de esta charla
es mostrarles qué encontramos: cómo se desempeñaron {r['laboratorios']} laboratorios clínicos
dominicanos frente a un criterio internacional, el error total permitido de CLIA. Y,
de cara al lema del congreso, cómo usamos un agente de inteligencia artificial para
automatizar la importación, el cálculo y los indicadores de desempeño, sin quitarle
la decisión a una persona.

El recorrido responde tres preguntas. [Señalar cada flecha, sin detenerse].
Primero, ¿quién verifica que el número es correcto? Segundo, ¿qué tan exactos fueron
los resultados de esta ronda? Y tercero, ¿cómo seguimos?: la IA en el procesamiento
del programa y qué podemos hacer.""")
    rect(s, 0.8, 1.7, 11.85, 1.15, "F3F6F8")
    rect(s, 0.8, 1.7, 0.09, 1.15, NARANJA)
    texto(s, 1.1, 1.71, 11.4, 1.13, [
        (f"**Objetivo:** describir el desempeño analítico de {r['laboratorios']} laboratorios "
         "clínicos dominicanos frente al error total permitido de CLIA, y mostrar cómo un "
         "agente de IA automatiza la importación, el cálculo y la generación de los "
         "indicadores de desempeño, con una persona que decide.",
         18, False, TINTA)], ancla=MSO_ANCHOR.MIDDLE)
    # Recorrido: tres flechas encadenadas (progresión, no lista), cada etapa con
    # la pregunta que responde. Azul para el diagnóstico, naranja para el
    # mañana —el naranja de las láminas de acción y de la compuerta humana—.
    recorrido = [
        ("1 · Medir la medición", NAVY,
         "¿Quién verifica que el número es correcto?",
         "Sistema de medida · control interno · ensayo de aptitud · criterio CLIA"),
        ("2 · Lo que encontramos", "1D5C85",
         "¿Qué tan exactos fueron los resultados?",
         f"{r['laboratorios']} laboratorios · {m['NAnalitos']} analitos · "
         f"{m['NRecibidos']} resultados"),
        ("3 · Modelando el mañana", NARANJA,
         "¿Cómo seguimos?",
         "IA en el procesamiento · decisión humana · qué hacer"),
    ]
    for i, (etapa, color, pregunta, detalle) in enumerate(recorrido):
        x = 0.8 + i * 3.95
        forma = MSO_SHAPE.PENTAGON if i == 0 else MSO_SHAPE.CHEVRON
        flecha = rect(s, x, 3.1, 4.0, 0.75, color, forma)
        tf = flecha.text_frame
        tf.word_wrap = False             # una sola línea: el chevrón estrecha el área
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.25 if i else 0.1)
        tf.margin_right = Inches(0.1)
        p_ = tf.paragraphs[0]
        p_.alignment = PP_ALIGN.CENTER
        _fmt(p_.add_run(), 17, True, "FFFFFF")
        p_.runs[0].text = etapa
        texto(s, x + 0.1, 4.0, 3.8, 0.8, [(pregunta, 19, True, NAVY)])
        texto(s, x + 0.1, 4.85, 3.8, 1.0, [(detalle, 15, False, GRIS_TXT)])

    # 5 ─ Sistema de medida ─────────────────────────────────────────────────
    s = mz.lamina("Un laboratorio es un sistema de medida",
                  "Y como todo sistema de medida, se verifica contra una referencia externa",
                  notas="""
Lo digo con el vocabulario de la metrología. El Vocabulario
Internacional de Metrología define un sistema de medida como un conjunto de
instrumentos y otros dispositivos, «incluidos reactivos e insumos». Esa
definición describe un laboratorio clínico casi palabra por palabra.

El resultado no lo produce el analizador solo: lo produce todo el sistema.
Una calibración desactualizada, un reactivo mal conservado o un procedimiento mal
ejecutado desplazan el resultado aunque el equipo funcione perfectamente.

Y a ningún instrumento de medida se le cree sin verificarlo contra una referencia.""")
    piezas = ["Analizador", "Reactivos", "Calibración", "Personal",
              "Procedimiento"]
    for i, t in enumerate(piezas):
        caja(s, 0.8, 1.75 + i * 0.8, 3.3, 0.66, [(t, True)], NAVY, size=19)
    flecha = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(4.35), Inches(3.15),
                                Inches(1.0), Inches(0.9))
    flecha.fill.solid(); flecha.fill.fore_color.rgb = rgb(CIAN); flecha.line.fill.background()
    caja(s, 5.6, 2.75, 2.6, 1.7, [("Resultado", True), ("del paciente", False)],
         NARANJA, size=22)
    texto(s, 8.6, 1.8, 4.2, 4.0, [
        ("**Sistema de medida**: uno o más instrumentos y otros dispositivos, "
         "**incluidos reactivos e insumos**, que producen los valores medidos.",
         17, False, TINTA),
        ("Si cualquier pieza se desplaza, el resultado se desplaza con ella.",
         17, False, GRIS_TXT),
    ], espacio=12)
    fuente(s, "Vocabulario Internacional de Metrología (VIM), JCGM 200:2012, "
              "definición 3.2 «measuring system» (traducción propia).")

    # 6 ─ Control interno ───────────────────────────────────────────────────
    fig_diana(FIGS / "diana.png")
    s = mz.lamina("El control interno no ve el sesgo",
                  "Verifica que el sistema repite, no que acierta",
                  notas="""
El control interno compara al laboratorio consigo mismo. Si el sistema está
desplazado, repite con excelente precisión un resultado desplazado, y el control
interno lo aprueba sin observaciones. Es la figura de la izquierda: puntos muy
juntos, todo parece en orden.

La figura de la derecha es lo que aporta el ensayo de aptitud: el centro
verdadero. Un proveedor independiente envía el mismo material a muchos
laboratorios y compara cada resultado con un valor asignado.

Es la única forma de responder la pregunta que importa: si este suero fuera de
un paciente, ¿el número que informo estaría dentro de lo clínicamente aceptable?""")
    imagen(s, FIGS / "diana.png", 1.6, 1.6, h=4.3)

    # 6b ─ Qué es un ensayo de aptitud ────────────────────────────────────
    # Va después del control interno (el problema) y antes de CONCALAB (quién lo
    # hace en el país). Definición y frecuencia citadas de los documentos
    # oficiales: ISO/IEC 17043:2023 §3.7 y 42 CFR §493.931(a).
    s = mz.lamina("¿Qué es un ensayo de aptitud?",
                  "La verificación externa que el control interno no puede hacer",
                  notas="""
Definición de la norma de proveedores de ensayos de aptitud, la ISO/IEC 17043:
evaluar el desempeño de los participantes frente a criterios establecidos de
antemano, comparando a los laboratorios entre sí.

En la práctica son tres pasos. Un mismo material llega a todos los laboratorios.
Cada uno lo mide como mide a sus pacientes, con su equipo y su rutina. Y el
proveedor compara cada resultado contra un valor asignado y un criterio fijado
antes de ver los datos.

¿Es obligatorio? Para los laboratorios clínicos acreditados, sí: la ISO 15189
exige participar en evaluación externa de la calidad, y la política de ILAC para
los organismos acreditadores la considera obligatoria cuando existe un programa
disponible y apropiado.

¿Con qué frecuencia? La norma no fija un número: cada laboratorio acreditado
define un plan de participación. Como referencia concreta, CLIA exige a los
programas de química de rutina al menos tres eventos al año, con cinco muestras
por analito en cada uno.
Una sola medición es una fotografía; la frecuencia es lo que permite ver si un
laboratorio mejora o se desvía.""")
    texto(s, 0.8, 1.68, 11.8, 1.1, [
        ("«Evaluación del desempeño de los participantes frente a criterios "
         "establecidos de antemano, mediante comparaciones interlaboratorio.»",
         22, False, NAVY),
        ("— ISO/IEC 17043:2023, definición 3.7 (traducción propia)", 13, False, GRIS_TXT),
    ], espacio=4)
    pasos = [("1 · Un mismo material", "llega a todos los laboratorios"),
             ("2 · Cada uno lo mide", "con su equipo y su rutina"),
             ("3 · Se compara", "contra un valor asignado y un criterio")]
    for i, (a, b) in enumerate(pasos):
        caja(s, 0.8 + i * 4.1, 3.0, 3.55, 1.15, [(a, True), (b, False)], NAVY, size=19)
        if i < 2:
            f = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(4.42 + i * 4.1),
                                   Inches(3.37), Inches(0.42), Inches(0.42))
            f.fill.solid(); f.fill.fore_color.rgb = rgb(CIAN); f.line.fill.background()
    rect(s, 0.8, 4.35, 11.85, 1.5, "F3F6F8")
    rect(s, 0.8, 4.35, 0.09, 1.5, NARANJA)
    texto(s, 1.1, 4.38, 11.4, 1.45, [
        ("**Laboratorios clínicos acreditados (ISO 15189):** participar es **obligatorio** "
         "cuando existe un programa apropiado.", 18, False, TINTA),
        ("**Frecuencia:** cada laboratorio la fija en un plan de participación. Como "
         "referencia, CLIA (EE. UU.) exige **3 eventos al año**, con **5 muestras por analito**.",
         18, False, TINTA),
    ], ancla=MSO_ANCHOR.MIDDLE, espacio=6)
    fuente(s, "ISO/IEC 17043:2023, def. 3.7 · ISO 15189:2022, 7.3.7.3, e ILAC-P9:01/2024 · "
              "CLIA: 42 CFR §493.931(a).")

    # 7 ─ CONCALAB ──────────────────────────────────────────────────────────
    s = mz.lamina("¿Quién hace esa verificación externa?",
                  "CONCALAB-UASD: Control de Calidad de Laboratorios de la UASD",
                  notas=f"""
Esa verificación externa es lo que hace CONCALAB-UASD, el programa de control de
calidad de laboratorios de la Universidad Autónoma de Santo Domingo.

Su origen es de 1983: el Laboratorio de Referencia de la UASD, creado por
maestras de la Escuela de Bioanálisis con la asesoría de la Dra. Blanca Odette
García Peguero, la misma que da nombre al premio a la calidad de este congreso.
Desde 2023 funciona con el nombre CONCALAB-UASD (Resolución 372-2023).

Lo que les presento hoy sale del informe de la ronda {codigo} de Química
Clínica, y del artículo que escribimos a partir de él. Las dos cosas están en
el QR. Los métodos estadísticos son los de la ISO 13528:2022.

Reconocer al equipo: el artículo es de un equipo de las escuelas de Bioanálisis
y de Matemática de la UASD; sus nombres están al final. Mi parte es la de
científico de datos: el procesamiento y la estadística de la ronda.""")
    hitos = [("1983", "Laboratorio de Referencia de la UASD, con la asesoría de la "
                      "**Dra. Blanca Odette García Peguero**"),
             ("2023", "Reconocido como **CONCALAB-UASD** (Resolución núm. 372-2023)"),
             ("Hoy", "Ensayos de aptitud con métodos de la **ISO 13528:2022**"),
             ("Esta charla", f"Informe **{codigo}**, Química Clínica, y el artículo derivado")]
    for i, (a, t) in enumerate(hitos):
        y = 1.8 + i * 1.02
        caja(s, 0.8, y, 2.0, 0.78, [(a, True)], NAVY if i < 3 else NARANJA, size=19)
        texto(s, 3.0, y + 0.06, 6.4, 0.9, [(t, 19, False, TINTA)],
              ancla=MSO_ANCHOR.MIDDLE)
    imagen(s, FIGS / "qr_portal.png", 10.05, 1.85, h=2.6)
    texto(s, 9.6, 4.5, 3.5, 0.8, [("Informe y artículo", 14, True, NAVY),
                                   (URL_PORTAL_CORTA, 12, False, GRIS_TXT)],
          alinear=PP_ALIGN.CENTER, espacio=0)
    fuente(s, "Fuente: concalabuasd.com › Nosotros › Historia.")

    # 8 ─ Criterio ──────────────────────────────────────────────────────────
    fig_criterio(FIGS / "criterio.png")
    s = mz.lamina("Cómo se evaluó: aptitud para el uso clínico",
                  "No contra el promedio de los participantes, sino contra un límite clínico",
                  notas="""
Dos decisiones metodológicas. Primera: el valor asignado es la media robusta de
los participantes, con el Algoritmo A de la ISO 13528. Segunda, y es la
novedad de esta ronda: no evaluamos contra la dispersión del grupo, que en un
grupo disperso es indulgente, sino contra el Error Total Permitido que CLIA, la
regulación estadounidense, fija analito por analito.

Escalamos el z para que z = 3 sea exactamente el límite de CLIA. Satisfactorio
hasta 2; alerta entre 2 y 3; no satisfactorio desde 3. Lipasa y bilirrubina
directa no están reguladas por CLIA: para esas usamos variación biológica.""")
    texto(s, 0.75, 1.7, 11.9, 1.6, [
        ("Valor asignado: **media robusta** de los participantes (ISO 13528:2022, Algoritmo A)",
         20, False, TINTA),
        ("Límite de aceptación: **Error Total Permitido (ETa) de CLIA**, fijado analito por analito",
         20, False, TINTA),
        ("**CLIA** (Clinical Laboratory Improvement Amendments): la regulación "
         "de los laboratorios clínicos de EE. UU.", 17, False, GRIS_TXT),
    ], espacio=6)
    imagen(s, FIGS / "criterio.png", 0.9, 3.2, h=2.65)
    fuente(s, "CLIA: 42 CFR §493.931 (regla final CMS-3355-F, 2022). Lipasa y bilirrubina "
              "directa: variación biológica (EFLM).")

    # ═════ ACTO II — El dato ════════════════════════════════════════════════

    # 9 ─ Participantes ─────────────────────────────────────────────────────
    s = mz.lamina("La ronda en cifras", f"{codigo} · Química Clínica",
                  notas=f"""
{r['laboratorios']} laboratorios, {m['NAnalitos']} analitos, {m['NRecibidos']} resultados recibidos.
{r['total']} recibieron calificación. Los demás no se calificaron: casi todos son de la
fosfatasa alcalina, que retiramos de la evaluación (lo explico más adelante), y unos
pocos de laboratorios cuyo grupo de comparación era demasiado pequeño para evaluarlos.

Una advertencia antes de ver las cifras, y no es de cortesía: la participación fue
voluntaria. No es una muestra del país. Puede que se hayan inscrito los más
preocupados por su calidad, o los mejor organizados. No lo sabemos, y por eso
hablamos de estos {r['laboratorios']} laboratorios, no de los laboratorios dominicanos.""")
    for i, (v, t) in enumerate([(str(r["laboratorios"]), "laboratorios\nparticipantes"),
                                (m["NAnalitos"], "analitos"),
                                (m["NRecibidos"], "resultados\nrecibidos"),
                                (str(r["total"]), "resultados\nevaluados")]):
        cifra(s, 0.75 + i * 3.0, 1.9, 2.9, v, t)
    rect(s, 0.75, 4.55, 11.9, 1.05, "F3F6F8")
    texto(s, 1.0, 4.62, 11.4, 0.95, [
        ("Participación **voluntaria**. Las cifras describen a estos laboratorios, "
         "**no al conjunto del país**.", 19, False, TINTA)], ancla=MSO_ANCHOR.MIDDLE)

    # 10 ─ Resultados ───────────────────────────────────────────────────────
    fig_resultados(d, FIGS / "resultados.png")
    de_cada = round(pct_no / 10)
    s = mz.lamina(f"{'Casi ' if pct_no < de_cada * 10 else ''}{de_cada} de cada 10 resultados, "
                  "fuera del límite clínico",
                  f"{r['total']} resultados evaluados frente al Error Total Permitido de CLIA",
                  notas=f"""
De {r['total']} resultados evaluados, {r['aceptables']} fueron satisfactorios ({num(r['aceptables']/r['total']*100)} %),
{r['cuestionables']} quedaron en alerta y {r['inaceptables']} fueron no satisfactorios ({num(pct_no)} %).

Un resultado no satisfactorio no es un número «un poco impreciso»: es un resultado
que, en un paciente, se sale de lo que el uso clínico tolera.

Las cifras completas, analito por analito, están en el informe y en el artículo (QR).""")
    imagen(s, FIGS / "resultados.png", 0.8, 1.9, w=11.7)
    texto(s, 0.8, 4.35, 11.8, 1.2, [
        ("Un resultado **no satisfactorio** no es «un poco impreciso»: en un paciente, "
         "se sale de lo que el **uso clínico** tolera.", 21, False, TINTA)])
    fuente(s, ctx)

    # 11 ─ Por laboratorio ──────────────────────────────────────────────────
    fig_estratos(d, FIGS / "estratos.png")
    s = mz.lamina(f"{g['conformes']} de {g['laboratorios']} laboratorios sin ninguna no conformidad",
                  "Un laboratorio es satisfactorio solo si ninguno de sus resultados quedó fuera del límite",
                  notas=f"""
Ahora la misma ronda, contada por laboratorio. La pregunta es otra: ¿cuántos
laboratorios no tuvieron ningún resultado no satisfactorio? {g['conformes']} de {g['laboratorios']}.

¿Por qué contar así? Porque un resultado errado que llega a un paciente es una falla,
sin importar cuántos otros salieron bien.

{g['estratos'][2]['laboratorios']} laboratorios acumularon tres o más no conformidades. La mediana fue de
{m['MedianaNoConformes']} por laboratorio. El desempeño insuficiente no es la cola de la
distribución: es lo habitual en este grupo.""")
    imagen(s, FIGS / "estratos.png", 0.8, 1.75, h=3.9)
    cifra(s, 9.7, 2.1, 3.0, m["MedianaNoConformes"],
          "no conformidades por laboratorio\n(mediana)", color=ROJO.lstrip("#"))
    fuente(s, ctx)

    # 12 ─ Concentración ────────────────────────────────────────────────────
    c = g["concentracion"]
    s = mz.lamina("No es un problema de unos pocos",
                  "Hay concentración, pero las no conformidades alcanzan a casi todos",
                  notas=f"""
La primera pregunta que uno se hace es: ¿no serán unos pocos laboratorios muy malos
los que arrastran la cifra? Revisamos eso.

Cada barra cuenta cuántos laboratorios tuvieron 0, 1, 2… resultados no
satisfactorios. Casi todo es rojo, y se reparte de 3 a más de 20. La línea marca
la mediana: {m['MedianaNoConformes']} por laboratorio.

Los {c['laboratorios']} laboratorios con más no conformidades suman el {num(c['pct'])} %. Es una
concentración real, pero el {num(100 - c['pct'])} % restante está repartido entre los otros
{g['laboratorios'] - c['laboratorios']}. Y {m['LabsConAlgunaNoConformidad']} de {g['laboratorios']} tuvieron al menos una.

Esto importa para la acción: si fuera un problema de pocos, la solución sería
dirigida. No lo es: es un problema del sistema.""")
    fig_distribucion(d, int(m["MedianaNoConformes"]), FIGS / "distribucion.png")
    imagen(s, FIGS / "distribucion.png", 0.7, 1.6, h=4.3)
    cifra(s, 9.55, 1.75, 3.2, f"{m['LabsConAlgunaNoConformidad']} de {g['laboratorios']}",
          "laboratorios con al menos\nuna no conformidad", color=ROJO.lstrip("#"), size=48)
    for i, e in enumerate(g["estratos"]):
        y = 4.05 + i * 0.5
        rect(s, 9.6, y + 0.1, 0.25, 0.25, e["color"].lstrip("#"))
        texto(s, 9.95, y, 3.0, 0.45, [(f"{e['nombre']}: **{e['laboratorios']}**", 15,
                                       False, TINTA)], ancla=MSO_ANCHOR.MIDDLE)
    fuente(s, ctx)

    # 13 ─ Por analito ──────────────────────────────────────────────────────
    fig_analitos(d, FIGS / "analitos.png")
    s = mz.lamina(f"Ningún analito supera el {m['DentroAnalitoMax']} %",
                  "% de resultados dentro del criterio de CLIA, por analito",
                  notas=f"""
El problema tampoco se localiza en unos pocos analitos. Ordenados de peor a mejor,
el más bajo queda en {m['DentroAnalitoMin']} % y el mejor no pasa de {m['DentroAnalitoMax']} %.

Un fallo puntual de un reactivo o de un lote afectaría a uno o dos analitos.
Lo que vemos es transversal: describe un sistema que, en conjunto, trabaja con
más error del que el uso clínico tolera.""")
    imagen(s, FIGS / "analitos.png", 0.65, 1.55, h=4.4)
    fuente(s, ctx + ". Fosfatasa alcalina: no evaluada.")

    # 13b ─ De cerca: un analito ──────────────────────────────────────────
    # Va DESPUÉS de la gráfica por analito, como ampliación de una de sus
    # barras: el porcentaje resume, los puntos muestran a cada laboratorio. Y
    # prepara «lo que descartamos»: el grueso coincide, así que no es el
    # material. Sin vocabulario clínico: el expositor es científico de datos y
    # la lectura clínica la hace la sala, que la conoce mejor (ver notas).
    eje = (k["valor_asignado"] * (1 - EXTREMOS_ESCALA),
           k["valor_asignado"] * (1 + EXTREMOS_ESCALA))
    fig_tira(k, FIGS / "ejemplo.png", paso=EJEMPLO_PASO, xlim=eje,
             unidad=k["eta"]["unidad"])
    kc = k["conteos"]
    u = k["eta"]["unidad"]
    pct_ronda = (r["aceptables"] + r["cuestionables"]) / r["total"] * 100
    en_eje = [v for v in kv if eje[0] <= v <= eje[1]]
    s = mz.lamina(f"De cerca: un mismo suero, {len(kv)} respuestas",
                  f"{k['nombre']} · valor asignado {num(k['valor_asignado'])} {u} · "
                  f"la banda celeste es el límite de CLIA · escala ±{EXTREMOS_ESCALA * 100:.0f} %",
                  notas=f"""
Veamos de cerca una de esas barras: la {k['nombre'].lower()}. La elegí porque es la que
todos conocemos, y porque su resultado, {num(kc['pct_dentro'])} % dentro del criterio, es
prácticamente el de toda la ronda, {num(pct_ronda)} %. No es el peor caso: es el caso típico.

Es un suero real: el mismo material llegó a {len(kv)} laboratorios. Cada punto es un
laboratorio. La línea es el valor asignado, {num(k['valor_asignado'])} {u}, y la banda
celeste es lo que CLIA acepta: ±{num(k['eta']['delta_e'])} {u}.

El grueso de los laboratorios está ahí. Pero para la misma muestra hay resultados
desde {num(min(en_eje))} hasta {num(max(en_eje))} {u}, y dos más fuera del gráfico (los
triángulos). [Mirar a la sala]. Ustedes saben mejor que yo lo que significa, para
el seguimiento de un paciente con diabetes, recibir uno u otro número.

Más allá del dato, la vida: detrás de cada punto hay un paciente.

Y fíjense en algo que nos lleva a la siguiente lámina: la mayoría coincide alrededor
del valor asignado. Si el material fuera el problema, se desviarían todos juntos.
NO mencionar códigos de laboratorio.""")
    imagen(s, FIGS / "ejemplo.png", 0.7, 1.6, h=4.3)
    texto(s, 9.85, 1.85, 3.0, 4.1, [
        (f"**{kc['A'] + kc['C']} de {len(kv)}**", 34, False, NAVY),
        ("dentro del límite de CLIA", 18, False, TINTA),
        (f"{num(kc['pct_dentro'])} % — casi lo mismo que toda la ronda ({num(pct_ronda)} %)",
         16, False, GRIS_TXT),
    ], espacio=6)
    fuente(s, f"Fuente: {codigo}, CONCALAB-UASD. Los triángulos son resultados fuera "
              "del eje, con su valor.")

    # 13c/13d ─ Los extremos ─────────────────────────────────────────────
    # Una lámina por analito, con la composición de la glucosa: en una sola
    # lámina con dos paneles se veía cargada. Misma escala relativa en ambas
    # (±EXTREMOS_ESCALA de X*) para que la dispersión se compare con justicia.
    notas_ext = {
        0: """
Para que no quede la duda de si la glucosa fue un caso elegido, veamos los dos
extremos, con la misma escala relativa.

El {n}: uno de los analitos más bajos de la ronda, {p} % dentro del criterio. Los
puntos se dispersan mucho más allá de la banda, hacia los dos lados. Es uno de los
analitos con los que se estima el riesgo cardiovascular.""",
        1: """
Y el otro extremo: la {n}, de los más altos, {p} % dentro del criterio. Con la misma
escala, el grupo está mucho más apretado alrededor del valor asignado.

Pero incluso en el mejor caso, uno de cada cinco laboratorios queda fuera.

Si preguntan por la bilirrubina directa, que tiene un porcentaje algo mayor: CLIA no
la regula y su límite, por variación biológica, es de ±44,5 %, más del doble que el
de los analitos de CLIA. Su porcentaje refleja un criterio más amplio, no un mejor
desempeño: de hecho, es el analito más disperso de la ronda.""",
    }
    for i, nombre in enumerate(EXTREMOS):
        a = buscar(d, nombre)
        xa = a["valor_asignado"]
        v = [l["resultado"] for l in a["laboratorios"] if l.get("resultado") is not None]
        c = a["conteos"]
        u = a["eta"]["unidad"]
        png = f"extremo_{i}.png"
        fig_tira(a, FIGS / png, paso=3,
                 xlim=(xa * (1 - EXTREMOS_ESCALA), xa * (1 + EXTREMOS_ESCALA)), unidad=u)
        titulo = "Entre los más bajos" if i == 0 else "Entre los más altos"
        s = mz.lamina(f"{titulo}: {a['nombre']}",
                      f"Valor asignado {num(xa)} {u} · la banda celeste es el límite de CLIA "
                      f"· escala ±{EXTREMOS_ESCALA * 100:.0f} %",
                      notas=notas_ext[i].format(n=a["nombre"], p=num(c["pct_dentro"])))
        imagen(s, FIGS / png, 0.7, 1.6, h=4.3)
        color = ROJO.lstrip("#") if i == 0 else VERDE.lstrip("#")
        texto(s, 9.85, 1.85, 3.0, 4.1, [
            (f"**{c['A'] + c['C']} de {len(v)}**", 34, False, color),
            ("dentro del límite de CLIA", 18, False, TINTA),
            (f"{num(c['pct_dentro'])} % — la ronda completa: {num(pct_ronda)} %", 16, False, GRIS_TXT),
        ], espacio=6)
        fuente(s, f"Fuente: {codigo}, CONCALAB-UASD. Los triángulos son resultados fuera "
                  "del eje, con su valor.")

    # 13e ─ Los dos errores ──────────────────────────────────────────────
    # Después de los tres analitos: el público acaba de ver puntos fuera de la
    # banda y aquí se dice qué le cuesta cada uno al paciente. «Error tipo I/II»
    # es vocabulario del expositor (estadística); «falso positivo/negativo», el
    # de la sala: van juntos. Contenido del propio artículo (introducción,
    # «Falsos positivos y falsos negativos»). Prepara la lámina de IA, que
    # «clasifica mal al paciente».
    s = mz.lamina("Más allá del dato: los dos errores que paga el paciente",
                  "Un resultado fuera del límite no es «impreciso»: produce una clasificación equivocada",
                  notas="""
En estadística los llamamos error tipo I y error tipo II. Ustedes los conocen como
falso positivo y falso negativo. [Señalar cada columna].

El falso positivo: un paciente sano con un resultado desviado hacia lo patológico.
Si nadie pide una prueba confirmatoria, queda medicado durante meses o años con un
fármaco que no necesita, con sus efectos adversos.

El falso negativo: un paciente enfermo con un resultado que cae en lo normal. Se va
a su casa tranquilo, y el tratamiento que sí necesita se retrasa. Es el más difícil
de detectar, porque un resultado normal no despierta sospechas.

Piensen en la glucosa que vimos: un laboratorio que mide alto puede diagnosticar
diabetes a quien no la tiene; uno que mide bajo puede dejarla pasar. Ustedes conocen
mejor que yo esos casos.

Y lo más importante: un sesgo sistemático no se equivoca con un paciente. Se
equivoca con una fracción de todos los que atiende ese laboratorio, todos los días,
mientras nadie lo detecte.""")
    errores = [("Falso positivo", "error tipo I", ROJO.lstrip("#"),
                "Un paciente **sano** recibe un diagnóstico y un tratamiento que **no necesita**: "
                "medicado durante meses o años, con sus efectos adversos."),
               ("Falso negativo", "error tipo II", NARANJA,
                "Un paciente **enfermo** recibe un resultado **normal**: se retrasa el "
                "tratamiento que sí necesita.")]
    for i, (a, b, color, cuerpo) in enumerate(errores):
        x = 0.8 + i * 6.0
        caja(s, x, 1.75, 5.8, 0.95, [(a, True), (b, False)], color, size=22)
        texto(s, x + 0.1, 2.85, 5.6, 1.4, [(cuerpo, 19, False, TINTA)])
    rect(s, 0.8, 4.45, 11.85, 1.15, "F3F6F8")
    rect(s, 0.8, 4.45, 0.09, 1.15, NAVY)
    texto(s, 1.1, 4.48, 11.4, 1.1, [
        ("Un sesgo sistemático no se equivoca con un paciente: **reclasifica a una "
         "fracción de todos los que atiende** el laboratorio.", 20, False, NAVY)],
          ancla=MSO_ANCHOR.MIDDLE)
    fuente(s, "Fuente: artículo del equipo CONCALAB-UASD (ResearchGate), sección 1.2, "
              "«Falsos positivos y falsos negativos».")

    # 14 ─ Lo que no lo explica ─────────────────────────────────────────────
    s = mz.lamina("Lo que descartamos antes de concluir",
                  "Ninguna de estas causas explica el resultado",
                  notas="""
Antes de publicar una cifra así, hay que descartar que el problema sea nuestro.

Unidades: auditamos cada no conforme para ver si se explicaba por haber reportado
en otra unidad. Ninguno.

Ceros: algunos laboratorios escriben 0 para decir «no realizado». Los excluimos
antes de calcular, para no castigar a nadie por un dato que no es una medición.

Plataforma: en fosfatasa alcalina, los equipos de química seca leían cerca de tres
veces más alto, y el proveedor del material confirmó que esos valores no eran
atribuibles al material. Era un problema de conmutabilidad del material, no de los
laboratorios, y la retiramos sin calificar. El desempeño global no cambió.""")
    filas = [("Errores de unidad", "Auditoría de cada no conforme: **ninguno** se explica por la unidad"),
             ("Ceros de «no realizado»", "**Excluidos** antes de calcular: no son mediciones"),
             ("Efecto de plataforma", "Fosfatasa alcalina **retirada sin calificar** "
                                      "(conmutabilidad del material); el resultado global no cambió")]
    for i, (a, t) in enumerate(filas):
        y = 1.8 + i * 1.35
        caja(s, 0.8, y, 3.6, 1.05, [(a, True)], NAVY, size=19)
        texto(s, 4.7, y, 8.0, 1.05, [(t, 19, False, TINTA)], ancla=MSO_ANCHOR.MIDDLE)

    # 15 ─ Decreto 350-04 ───────────────────────────────────────────────────
    s = mz.lamina("¿Por qué era esperable?",
                  "Decreto 350-04: Reglamento de Habilitación de los Laboratorios Clínicos",
                  notas="""
Un resultado así obliga a preguntar cómo llegamos aquí. El marco regulatorio da
buena parte de la respuesta.

El Decreto 350-04 sí menciona la evaluación externa. Le pide al director «tomar
las iniciativas para la instalación» de los programas (artículo 26) y obliga a
conservar la documentación de los programas «que sean realizados» (artículo 30).

Fíjense en los verbos. Se pide tomar iniciativas, no participar. Y la obligación
documental solo alcanza a quien ya participa. Lo que falta no es la exigencia:
es todo lo que la haría comprobable.

Y el decreto es de 2004: anterior a las normas vigentes de laboratorios clínicos
y de ensayos de aptitud.""")
    texto(s, 0.8, 1.75, 11.8, 1.5, [
        ("«…**tomar las iniciativas** para la instalación de los Programas de Garantía "
         "Interna y Evaluación Externa de la Calidad»", 22, False, NAVY),
        ("— Artículo 26, inciso e (deber del director del laboratorio)", 14, False, GRIS_TXT),
    ], espacio=6)
    texto(s, 0.8, 3.3, 5.0, 0.5, [("Lo que el reglamento no define:", 20, True, TINTA)])
    for i, t in enumerate(["Cómo se acredita que se participó",
                           "Qué desempeño es aceptable",
                           "Qué ocurre si no se alcanza"]):
        caja(s, 0.8 + i * 4.0, 3.95, 3.75, 1.2, [(t, True)], NARANJA, size=19)
    fuente(s, "Decreto 350-04 (20 de abril de 2004), art. 26 inciso e y art. 30 párrafo II.")

    # 16 ─ Cobertura y otros países ─────────────────────────────────────────
    # El denominador NO es un dato público: es la cifra del MSP que recogió la
    # prensa. Por eso va redondeado («≈ 6 %», no «6.2 %», que sugiere una
    # precisión que no tiene) y rotulado como estimación en la propia lámina.
    cobertura = round(float(m["CoberturaPais"]))
    s = mz.lamina("¿Cuánto se equivoca la red del país? No lo sabemos",
                  "No existe un registro público de laboratorios: el total es una estimación",
                  notas=f"""
¿Cuántos laboratorios hay en el país? No lo sabemos con exactitud: no existe un
registro público. La única cifra disponible es la que el Ministerio de Salud dio a
la prensa en {m['FuenteDenominadorAnio']}: unos {m['LabsRegistradosMSP']} laboratorios y centros de diagnóstico.
Tomándola como orden de magnitud, nuestros {r['laboratorios']} participantes son alrededor del
{cobertura} %.

Que ni siquiera sepamos cuántos laboratorios hay ya dice algo del sistema.

Por eso el hallazgo más importante no es el {num(pct_no)} %. Es que el país no tiene
información para afirmar que su red diagnóstica mide bien, ni para corregirla si
mide mal.

Otros países lo resolvieron haciendo obligatoria la participación periódica:
Estados Unidos, México, Brasil. Exigirla no pondría al país por delante de nadie:
lo pondría en el grupo que ya lo hace.""")
    cifra(s, 0.8, 1.8, 4.6, f"≈ {cobertura} %",
          f"{r['laboratorios']} de unos {m['LabsRegistradosMSP']} laboratorios del país\n"
          "participaron en esta ronda (estimación)", color=NAVY, size=60)
    texto(s, 6.0, 1.75, 6.7, 0.5, [("La participación en ensayos de aptitud ya es "
                                    "obligatoria en:", 19, True, TINTA)])
    for i, (pais, norma) in enumerate([("Estados Unidos", "42 CFR §493.801"),
                                       ("México", "NOM-007-SSA3-2011"),
                                       ("Brasil", "RDC ANVISA 302/2005")]):
        y = 2.65 + i * 0.95
        caja(s, 6.0, y, 2.7, 0.75, [(pais, True)], NAVY, size=18)
        texto(s, 8.9, y, 3.8, 0.75, [(norma, 18, False, TINTA)], ancla=MSO_ANCHOR.MIDDLE)
    fuente(s, f"Estimación: cifra del Ministerio de Salud Pública citada por Listín Diario "
              f"({m['FuenteDenominadorAnio']}). No hay registro público; se usa solo como orden de magnitud.")

    # ═════ ACTO III — «Modelando el mañana… con sentido humano» ═════════════

    # 17 ─ La IA recibe el dato ───────────────────────────────────────────
    # El caso es la IA como APOYO AL MÉDICO, que recibe el resultado como
    # entrada; no una IA entrenada con resultados de laboratorio (en el país no
    # es el escenario realista). Ejemplo: HDL → riesgo cardiovascular, que es el
    # analito de la lámina «Entre los más bajos». Cifras del JSON.
    hdl = buscar(d, EXTREMOS[0])
    hc = hdl["conteos"]
    hdl_n = hc["A"] + hc["C"] + hc["I"]
    s = mz.lamina("Modelando el mañana con inteligencia artificial",
                  "La IA de diagnóstico no ve al paciente: ve el número que le entrega el laboratorio",
                  notas=f"""
El lema habla de modelar el mañana con innovación inteligente, y la inteligencia
artificial ya está llegando a la consulta como apoyo al médico.

Un ejemplo. Un médico usa una herramienta de IA para estimar el riesgo
cardiovascular de su paciente. Esa herramienta usa, entre otros datos, el
colesterol HDL. Se desarrolló y se validó en otros países, con laboratorios que
cumplen especificaciones como las de CLIA: da por hecho que el número que recibe
es correcto.

Pero el número viene de un laboratorio. Y en esta ronda, en el HDL, solo {hc['A'] + hc['C']} de
{hdl_n} laboratorios quedaron dentro del límite de CLIA, como vimos antes. La
herramienta calcula perfecto a partir de un dato equivocado.

Dos ideas. [Señalar el recuadro izquierdo]. La IA no puede corregir lo que no ve:
recibe un número, no sabe si ese laboratorio mide alto o bajo, y ningún algoritmo
lo detecta desde fuera. Lo detecta un ensayo de aptitud. [Recuadro derecho]. Y la
IA le da autoridad al error: es fácil dudar de un número raro; es más difícil
dudar de lo que recomienda la IA.

Como científico de datos lo digo así: un modelo es tan bueno como el dato que le
entra. Primero, exactitud verificada; después, inteligencia artificial.

[Transición a la siguiente lámina]: «Acabamos de ver que la IA necesita un número
verificado. ¿Quién lo verifica? El ensayo de aptitud. Y para producir esa
verificación nosotros también usamos inteligencia artificial, pero de otro tipo: no
diagnostica, construye y opera el procesamiento de la ronda. Y con la misma
condición que pedimos en la consulta: decide una persona.»""")
    pasos = [("Laboratorio", "informa el HDL", ROJO.lstrip("#")),
             ("IA de apoyo", "estima el riesgo cardiovascular", NAVY),
             ("Médico", "decide el tratamiento", NAVY),
             ("Paciente", "recibe la decisión", NAVY)]
    for i, (a, b, color) in enumerate(pasos):
        x = 0.8 + i * 3.1
        caja(s, x, 1.75, 2.5, 1.15, [(a, True), (b, False)], color, size=19)
        if i < 3:
            f = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 2.58),
                                   Inches(2.12), Inches(0.42), Inches(0.42))
            f.fill.solid(); f.fill.fore_color.rgb = rgb(CIAN); f.line.fill.background()
    texto(s, 0.75, 2.98, 3.4, 0.75, [
        (f"En esta ronda: solo **{hc['A'] + hc['C']} de {hdl_n}** dentro del límite de CLIA",
         15, False, ROJO.lstrip("#"))])
    ideas = [("La IA no corrige lo que no ve.",
              "Recibe un número; no sabe si ese laboratorio mide alto o bajo."),
             ("La IA le da autoridad al error.",
              "Es fácil dudar de un número raro; es más difícil dudar de lo que recomienda la IA.")]
    for i, (a, b) in enumerate(ideas):
        x = 0.8 + i * 6.0
        rect(s, x, 3.85, 5.8, 1.2, "F3F6F8")
        rect(s, x, 3.85, 0.09, 1.2, NARANJA)
        texto(s, x + 0.25, 3.88, 5.45, 1.15, [(a, 19, True, TINTA), (b, 16, False, GRIS_TXT)],
              ancla=MSO_ANCHOR.MIDDLE, espacio=4)
    texto(s, 0.8, 5.25, 11.9, 0.6, [
        ("Lo que verifica el número es el **ensayo de aptitud**. Primero exactitud; "
         "después, inteligencia artificial.", 20, False, NAVY)])

    # 18 ─ Con sentido humano ───────────────────────────────────────────────
    # Puente con la lámina anterior: allí, la IA de diagnóstico necesita un
    # número verificado; aquí, cómo se produce esa verificación. También con IA,
    # pero de otro tipo: un agente que construye y opera el procesamiento. Tres
    # capas que la lámina distingue a propósito, porque «la IA calcula tu
    # Z-Score» haría desconfiar de los resultados: la IA construye y opera, el
    # código auditable calcula, una persona decide.
    s = mz.lamina("CONCALAB-UASD: IA con sentido humano",
                  "Así se produce esa verificación: un agente de IA, código auditable "
                  "y una persona que decide",
                  notas="""
[Viene de la transición de la lámina anterior].

Aquí también usamos inteligencia artificial, pero de otro tipo: no diagnostica.
Es un agente de IA que construye y opera el procesamiento de la ronda: la
importación de los resultados del formulario web, el cálculo, la validación de
cada cifra, la auditoría de unidades, el informe web y el PDF. Lo que antes
tomaba semanas de hojas de cálculo hoy toma minutos y es reproducible.

Una precisión importante: la IA no calcula sus Z-Score. Las cifras las calcula
código auditable —la media robusta de la ISO 13528 y el límite de CLIA—, que con
el mismo dato da siempre el mismo resultado. Y un validador recalcula cada número
y detiene todo si algo no cuadra.

Y el proceso se detiene a propósito antes de publicar. Hay una compuerta donde
decide una persona: qué analitos se evalúan por grupo de pares, cuáles se
publican sin calificar, qué casos se consultan con el laboratorio.

El ejemplo es la fosfatasa alcalina. Ningún algoritmo podía saber que el material
no era conmutable con ciertas plataformas: lo supimos consultando al proveedor del
material. La IA construye, el código calcula, la persona decide. Eso es, para
nosotros, innovación con sentido humano.

(Si preguntan qué agente: Claude Code, de Anthropic.)""")
    caja(s, 0.7, 1.65, 8.75, 0.45, [("Construido y operado con un agente de IA", True)],
         "D6F3F7", tinta=NAVY, size=16)
    etapas = ["Resultados\n(formulario web)", "Cálculo\nrobusto", "Validación\nautomática",
              "Auditoría\nde unidades"]
    for i, t in enumerate(etapas):
        caja(s, 0.7 + i * 2.25, 2.2, 2.0, 1.1, [(t, True)], NAVY, size=16)
    caja(s, 9.7, 1.65, 2.95, 1.65, [("Compuerta humana", True),
                                    ("como el médico: decide una persona", False)],
         NARANJA, size=20)
    caja(s, 0.7, 3.45, 8.75, 0.6, [("Las cifras las calcula código auditable: "
                                    "mismo dato, mismo resultado", True)],
         "DCE6EB", tinta=NAVY, size=17)
    texto(s, 0.8, 4.3, 11.9, 1.6, [
        ("La IA **construye y opera**. El código **calcula**. Una persona **decide** qué "
         "se evalúa, qué se publica sin calificar y qué se consulta con el laboratorio.",
         21, False, TINTA),
    ])

    # 19 ─ Qué hacer ────────────────────────────────────────────────────────
    s = mz.lamina("¿Qué podemos hacer?", notas="""
Tres actores, tres acciones.

El laboratorio: participar de forma periódica. Un resultado no satisfactorio no es
una sanción, es información que el control interno no puede dar. Y cuando aparece,
investigar el sesgo: calibración, reactivos, trazabilidad.

La autoridad sanitaria: la brecha del Decreto 350-04 es acotada y su corrección
también. Convertir la participación periódica en requisito de habilitación, con un
criterio de desempeño definido.

El programa: rondas periódicas. Una ronda es una fotografía; varias rondas permiten
ver la tendencia y medir la mejora.""")
    cols = [("Laboratorio", ["Participar de forma periódica",
                             "Leer el no satisfactorio como información, no como sanción",
                             "Investigar el sesgo: calibración, reactivos, trazabilidad, condiciones ambientales"]),
            ("Autoridad sanitaria", ["Participación periódica como requisito de habilitación",
                                     "Criterio de desempeño aceptable definido"]),
            ("Programa", ["Rondas periódicas para medir la tendencia",
                          "Ampliar la cobertura nacional"])]
    for i, (a, items) in enumerate(cols):
        x = 0.75 + i * 4.05
        caja(s, x, 1.75, 3.8, 0.75, [(a, True)], NAVY, size=21)
        texto(s, x + 0.05, 2.65, 3.7, 3.2, [(f"• {t}", 18, False, TINTA) for t in items],
              espacio=10)

    # 20 ─ Conclusiones ─────────────────────────────────────────────────────
    s = mz.lamina("Conclusiones", notas="""
Tres ideas para llevarse.

Uno: en estos laboratorios, el desempeño frente a un criterio clínico internacional
fue insuficiente de forma generalizada, en todos los analitos y no solo en unos pocos
laboratorios.

Dos: es la consecuencia esperable de dos décadas sin retroalimentación externa
comprobable, no una anomalía ni una culpa individual.

Tres: antes de automatizar, hay que verificar. La exactitud es la condición para que
la innovación inteligente tenga sentido humano.""")
    concl = [f"En estos {r['laboratorios']} laboratorios, el desempeño frente a un criterio clínico "
             "internacional fue **insuficiente de forma generalizada**",
             "Es la consecuencia esperable de **dos décadas sin retroalimentación externa "
             "comprobable**, no una culpa individual",
             "Antes de automatizar, **verificar**: la exactitud es la condición de la "
             "innovación con sentido humano"]
    for i, t in enumerate(concl):
        y = 1.8 + i * 1.35
        caja(s, 0.8, y, 0.95, 0.95, [(str(i + 1), True)], NARANJA, size=28)
        texto(s, 2.0, y - 0.05, 10.7, 1.1, [(t, 21, False, TINTA)], ancla=MSO_ANCHOR.MIDDLE)

    # 21 ─ Para saber más ───────────────────────────────────────────────────
    s = mz.lamina("Para saber más", notas="""
Todo lo que mostré está publicado. El primer QR lleva al portal de CONCALAB, con el
informe completo de la ronda: cada laboratorio puede buscar su código y ver cada
analito. El segundo, al artículo en ResearchGate.

Y quiero reconocer al equipo: este trabajo es de un equipo de las escuelas de
Bioanálisis y de Matemática de la UASD. Sus nombres están en pantalla.""")
    for i, (img, a, b) in enumerate([
            ("qr_portal.png", "Informe EA-001-2026 y presentación", URL_PORTAL_CORTA),
            ("qr_articulo.png", "Artículo (ResearchGate)",
             "Analytical performance in clinical chemistry…")]):
        x = 0.8 + i * 3.45
        imagen(s, FIGS / img, x + 0.3, 1.75, h=2.55)
        texto(s, x - 0.1, 4.35, 3.35, 1.0, [(a, 15, True, NAVY), (b, 12, False, GRIS_TXT)],
              alinear=PP_ALIGN.CENTER, espacio=2)
    texto(s, 8.1, 1.75, 4.6, 0.5, [("Autores", 20, True, NAVY)])
    texto(s, 8.1, 2.3, 4.6, 3.4, [(a, 16, False, TINTA) for a in AUTORES] +
          [("Universidad Autónoma de Santo Domingo", 14, False, GRIS_TXT)], espacio=5)

    # 22 ─ Preguntas ────────────────────────────────────────────────────────
    s = mz.lamina("Gracias", notas="Abrir preguntas. Ver la hoja de preguntas probables.")
    texto(s, 0.8, 2.0, 7.5, 2.5, [
        ("¿Preguntas?", 44, True, NAVY),
        ("Más allá del dato, la vida.", 26, False, GRIS_TXT),
    ], espacio=14)
    imagen(s, FIGS / "qr_portal.png", 9.4, 1.8, h=2.6)
    texto(s, 8.9, 4.45, 3.6, 0.8, [("concalabuasd.com", 16, True, NAVY)],
          alinear=PP_ALIGN.CENTER)
    return mz


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--codigo", default="EA-001-2026")
    ap.add_argument("--pdf", action="store_true",
                    help="exporta además un PDF de vista previa con LibreOffice")
    ap.add_argument("--portal", action="store_true",
                    help=f"exporta el PDF que se publica en el portal ({PDF_PORTAL.name})")
    args = ap.parse_args()

    d = json.loads((RAIZ / "data" / "informes" / f"{args.codigo}-quimica-clia.json")
                   .read_text(encoding="utf-8"))
    if d.get("modelo") != "clia":
        raise SystemExit("El JSON no declara modelo: clia.")
    m = leer_macros()
    if m.get("Codigo") != args.codigo:
        raise SystemExit(f"paper/generado/macros.tex es de {m.get('Codigo')}, no de "
                         f"{args.codigo}: correr scripts/paper_datos.py primero.")

    CARPETA.mkdir(parents=True, exist_ok=True)
    destino = CARPETA / ARCHIVO
    construir(d, m).guardar(destino)
    print(f"✓ {destino.relative_to(RAIZ)}")
    if args.pdf or args.portal:
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir",
                        str(FIGS), str(destino)], check=True, capture_output=True)
        previa = FIGS / destino.with_suffix(".pdf").name
        print(f"✓ vista previa: {previa.relative_to(RAIZ)}")
        if args.portal:
            PDF_PORTAL.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(previa, PDF_PORTAL)
            print(f"✓ portal: {PDF_PORTAL.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
