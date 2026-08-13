#!/usr/bin/env python3
"""Informe entregable en PDF de una ronda de ensayo de aptitud.

Lee el MISMO JSON que dibuja la página web y produce un PDF vectorial con
LaTeX. Que la fuente sea el JSON no es una comodidad: es lo que garantiza que
el PDF entregado y el informe publicado digan exactamente lo mismo, y que
`validar_informe.py` audite ambos a la vez. Ninguna cifra se calcula aquí.

    conda activate concalab
    python scripts/informe_pdf.py --codigo EA-001-2026

Salida: publicaciones/informes/<codigo>-informe.pdf
Intermedios (figuras + .tex): support/pdf_<codigo>/   (no se despliega)

Las figuras se emiten como PDF vectorial, no como imagen: el informe se
imprime y se amplía, y una captura rasterizada del navegador perdería
justamente la nitidez de las 53 gráficas.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

RAIZ = Path(__file__).resolve().parent.parent

# Paleta del sitio (css/main.css). Estado A/C/I y color institucional.
AZUL = "#003f87"
ORO = "#fdb913"
VERDE = "#28a745"
AMARILLO = "#ffc107"
ROJO = "#dc3545"
GRIS = "#9aa3b2"
# Identidad de grupo de pares — nunca los colores de estado (js/informe.js).
COLOR_GRUPO = ["#1f4e9c", "#c77f0a", "#00857a", "#7b4ea3"]

Z_VISTA = 5      # rango visible del histograma, en σ*
Z_VIS = 6        # recorte del eje de Z-Score

plt.rcParams.update({
    "font.size": 8,
    "axes.titlesize": 9.5,
    "axes.titlecolor": "#1a237e",
    "axes.labelsize": 8,
    "axes.edgecolor": "#cccccc",
    "grid.color": "#eeeeee",
    "figure.dpi": 110,
    "pdf.fonttype": 42,
})


# ── Utilidades ────────────────────────────────────────────────────────────

# Símbolos Unicode presentes en los textos del JSON, con su equivalente LaTeX.
SIMBOLOS = {
    "σ": r"$\sigma$", "µ": r"$\mu$", "α": r"$\alpha$", "β": r"$\beta$",
    "δ": r"$\delta$", "Δ": r"$\Delta$", "≤": r"$\le$", "≥": r"$\ge$",
    "≈": r"$\approx$", "×": r"$\times$", "±": r"$\pm$",
    "⅔": r"$\tfrac{2}{3}$", "⅓": r"$\tfrac{1}{3}$",
    "→": r"$\rightarrow$", "↔": r"$\leftrightarrow$",
    "≠": r"$\neq$", "‰": r"\textperthousand{}",
    "–": r"\textendash{}", "—": r"\textemdash{}", "…": r"\dots{}",
    "“": "``", "”": "''", "‘": "`", "’": "'",
}


def esc(t):
    """Escapa texto para LaTeX. Los nombres de analito traen paréntesis y
    acentos; el % de un CV rompería la compilación en silencio."""
    if t is None:
        return ""
    t = str(t)
    reemplazos = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    for a, b in reemplazos.items():
        t = t.replace(a, b)
    # Los textos del JSON (criterios, justificaciones) traen símbolos
    # matemáticos que utf8+T1 no sabe componer y que abortan la compilación.
    for a, b in SIMBOLOS.items():
        t = t.replace(a, b)
    return t


def desmarcar(html):
    """Las notas del proveedor viven en el JSON como HTML (las lee la web).
    Aquí se convierten a LaTeX conservando el énfasis, que es parte de la
    declaración: lo que va en negrita es la decisión, no adorno."""
    t = html or ""
    t = re.sub(r"<br\s*/?>", "\n\n", t)
    partes = re.split(r"(<strong>.*?</strong>|<em>.*?</em>)", t, flags=re.S)
    out = []
    for p in partes:
        if p.startswith("<strong>"):
            out.append(r"\textbf{" + esc(re.sub(r"</?strong>", "", p)) + "}")
        elif p.startswith("<em>"):
            out.append(r"\emph{" + esc(re.sub(r"</?em>", "", p)) + "}")
        else:
            out.append(esc(re.sub(r"<[^>]+>", "", p)))
    return "".join(out).strip()


def plural(n, singular, plural_):
    return f"{n} {singular if n == 1 else plural_}"


def es_pares(a):
    return a["evaluacion"] == "grupo_pares"


def es_no_evaluado(a):
    return a["evaluacion"] == "no_evaluada"


def color_grupo(a, nombre):
    evs = [g["nombre"] for g in a.get("grupos", []) if g["evaluado"]]
    return COLOR_GRUPO[evs.index(nombre) % len(COLOR_GRUPO)] if nombre in evs else GRIS


def z_color(z):
    az = abs(z)
    return VERDE if az <= 2 else (AMARILLO if az < 3 else ROJO)


def eta_label(eta, unidad):
    """Etiqueta del Error Total Permitido: la regla declarada y el δE resuelto.
    Misma lógica que etaLabel() en js/informe.js."""
    if not eta:
        return ""
    partes = []
    if eta.get("pct") is not None:
        partes.append(f"±{eta['pct']}\\%")
    if eta.get("abs") is not None:
        partes.append(f"±{eta['abs']} {esc(eta.get('unidad') or unidad)}")
    regla = (" o " if eta.get("regla") == "mayor" else " ").join(partes)
    solo_abs = eta.get("pct") is None and eta.get("abs") is not None
    resuelto = ""
    if not solo_abs and eta.get("delta_e") is not None:
        resuelto = f" (±{eta['delta_e']:.2f} {esc(unidad)})"
    vb = r" \emph{(EFLM)}" if "EFLM" in (eta.get("fuente") or "") else ""
    return regla + resuelto + vb


def slug(nombre):
    return re.sub(r"[^A-Za-z0-9]+", "-", nombre).strip("-").lower()


# ── Figuras ───────────────────────────────────────────────────────────────

def _fmt(destino):
    """El formato sale de la extensión, no fijo en 'pdf'.

    Estas mismas figuras las reusa scripts/presentacion.py en SVG: son las
    cifras del informe y redibujarlas con otro código las dejaría fuera de lo
    que audita validar_informe.py."""
    return os.path.splitext(destino)[1].lstrip(".") or "pdf"


def fig_histograma(a, destino):
    """Distribución de resultados. Réplica del histograma de la web:
    rango acotado a |z| ≤ 5 sobre σ*, banda de aceptación X* ± ETa, y los
    laboratorios que caen fuera dibujados en el borde y nombrados — contar
    cuántos quedaron fuera no basta, cada lab debe localizarse."""
    resultados = [l["resultado"] for l in a["laboratorios"]]
    unidad = a["unidad"]

    if es_pares(a):
        centros = [{"nombre": g["nombre"], "x": g["valor_asignado"],
                    "s": g["sd_robusta"], "color": color_grupo(a, g["nombre"])}
                   for g in a["grupos"] if g["evaluado"]]
    else:
        centros = [{"nombre": None, "x": a["valor_asignado"],
                    "s": a["sd_robusta"], "color": ROJO}]

    x_min = min(c["x"] - Z_VISTA * c["s"] for c in centros)
    x_max = max(c["x"] + Z_VISTA * c["s"] for c in centros)

    fig, ax = plt.subplots(figsize=(7.0, 2.55))
    n_bins = max(8, min(20, len(resultados) // 2))
    bordes = np.linspace(x_min, x_max, n_bins + 1)

    # Banda de aceptación: solo con un criterio único. Con grupos de pares
    # cada uno tendría el suyo y se solaparían.
    if len(centros) == 1:
        semi = a["eta"]["delta_e"] if a.get("eta") else 2 * centros[0]["s"]
        ax.axvspan(centros[0]["x"] - semi, centros[0]["x"] + semi,
                   color=VERDE, alpha=0.10, zorder=0)

    if es_pares(a):
        for g in a["grupos"]:
            vals = [l["resultado"] for l in a["laboratorios"]
                    if l.get("grupo") == g["nombre"]]
            c = color_grupo(a, g["nombre"]) if g["evaluado"] else GRIS
            ax.hist(vals, bins=bordes, color=c, alpha=0.72, edgecolor=c,
                    linewidth=0.8, label=f"{g['nombre']} (n={g['n']})")
        ax.legend(fontsize=6.5, loc="upper right", framealpha=0.9)
    else:
        ax.hist(resultados, bins=bordes, color="#1a237e", alpha=0.70,
                edgecolor="#1a237e", linewidth=0.8)

    for k, c in enumerate(centros):
        ax.axvline(c["x"], color=c["color"], linestyle="--", linewidth=1.5)
        ax.annotate(f"X* = {c['x']}", xy=(c["x"], 1 - k * 0.09),
                    xycoords=("data", "axes fraction"), xytext=(3, -8),
                    textcoords="offset points", color=c["color"], fontsize=7)

    # Fuera del rango visible: marcadores en el borde hacia el que se salen.
    fuera = sorted((l for l in a["laboratorios"]
                    if l["resultado"] < x_min or l["resultado"] > x_max),
                   key=lambda l: l["resultado"])
    for l in fuera:
        borde = x_min if l["resultado"] < x_min else x_max
        marca = "<" if l["resultado"] < x_min else ">"
        ax.plot([borde], [0], marker=marca, markersize=7, color=ROJO,
                markeredgecolor="white", markeredgewidth=0.8, clip_on=False,
                zorder=5)
    if fuera:
        txt = "  ·  ".join(
            f"{l['id']} = {l['resultado']} {unidad}"
            + ("" if l["z_score"] is None else f" (z {l['z_score']:+.1f})")
            for l in fuera[:3])
        if len(fuera) > 3:
            txt += f"  ·  y {len(fuera) - 3} más"
        ax.set_title(f"▶ Fuera del rango visible: {txt}", fontsize=6,
                     color="#c62828", loc="right", pad=2)

    ax.set_xlim(x_min, x_max)
    ax.set_xlabel(f"Resultado ({unidad})")
    ax.set_ylabel("Frecuencia (n.º de laboratorios)")
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(destino, format=_fmt(destino), bbox_inches="tight")
    plt.close(fig)


def fig_zscore(a, destino):
    """Z-Score por laboratorio. Eje acotado a |z| ≤ 6 (se han visto z de +56,
    que aplastan las otras 36 barras contra el cero); las barras recortadas
    conservan su valor real en la etiqueta. Solo se rotula |z| > 2."""
    labs = [l for l in a["laboratorios"] if l["z_score"] is not None]
    sin_ev = [l for l in a["laboratorios"] if l["z_score"] is None]
    labs = sorted(labs, key=lambda l: l["z_score"])

    fig, ax = plt.subplots(figsize=(7.0, 2.55))
    xs = np.arange(len(labs))
    zs = [l["z_score"] for l in labs]
    z_plot = [max(-Z_VIS, min(Z_VIS, z)) for z in zs]
    ax.axhspan(-2, 2, color=VERDE, alpha=0.05, zorder=0)
    ax.bar(xs, z_plot, color=[z_color(z) for z in zs],
           edgecolor="black", linewidth=0.3, zorder=2)

    for x, z, zp in zip(xs, zs, z_plot):
        if abs(z) > 2:
            ax.annotate(f"{z:.1f}", xy=(x, zp), fontsize=5.5, rotation=90,
                        ha="center", va="bottom" if zp >= 0 else "top",
                        xytext=(0, 2 if zp >= 0 else -2),
                        textcoords="offset points")

    for y, c, ls in ((2, "orange", "--"), (-2, "orange", "--"),
                     (3, "red", ":"), (-3, "red", ":")):
        ax.axhline(y, color=c, linewidth=1.0, linestyle=ls)
        ax.annotate(f"z={y:+d}", xy=(1.005, y), xycoords=("axes fraction", "data"),
                    fontsize=5.5, color=c, va="center")
    ax.axhline(0, color="#666", linewidth=0.8)

    ax.set_xticks(xs)
    ax.set_xticklabels([l["id"] for l in labs], rotation=90, fontsize=5.5)
    ax.set_ylim(-Z_VIS - 0.8, Z_VIS + 0.8)
    ax.set_ylabel("Z-Score")
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)

    notas = []
    if es_pares(a):
        notas.append("Z calculado dentro de cada grupo de pares")
    recortadas = sum(1 for z in zs if abs(z) > Z_VIS)
    if recortadas:
        notas.append(f"{recortadas} lab. con |z| > {Z_VIS}: barra al tope, "
                     "valor real en la etiqueta")
    if sin_ev:
        notas.append("Sin Z-Score (grupo de pares insuficiente): "
                     + ", ".join(l["id"] for l in sin_ev))
    if notas:
        ax.set_title(" · ".join(notas), fontsize=6, color="#6c757d", loc="left",
                     pad=3)
    fig.tight_layout()
    fig.savefig(destino, format=_fmt(destino), bbox_inches="tight")
    plt.close(fig)


def fig_no_evaluado(a, destino_hist, destino_barras):
    """Analito sin calificación: histograma y barras del RESULTADO CRUDO.
    Deliberadamente sin banda de aceptación, sin línea de X* y sin Z-Score —
    cada uno de esos elementos afirma un criterio de conformidad, que es
    justamente lo que la ronda declara que no puede sostener aquí."""
    resultados = [l["resultado"] for l in a["laboratorios"]]
    ref = a.get("referencia_descriptiva", {})
    unidad = a["unidad"]

    fig, ax = plt.subplots(figsize=(7.0, 2.55))
    ax.hist(resultados, bins=18, color=GRIS, alpha=0.8, edgecolor="#7a828f",
            linewidth=0.8)
    if ref.get("mediana") is not None:
        ax.axvline(ref["mediana"], color="#4a5568", linestyle="--", linewidth=1.4)
        ax.annotate(f"Mediana = {ref['mediana']} (referencia descriptiva)",
                    xy=(ref["mediana"], 1), xycoords=("data", "axes fraction"),
                    xytext=(3, -9), textcoords="offset points",
                    color="#4a5568", fontsize=7)
    ax.set_xlabel(f"Resultado ({unidad})")
    ax.set_ylabel("Frecuencia (n.º de laboratorios)")
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(destino_hist, format=_fmt(destino_hist), bbox_inches="tight")
    plt.close(fig)

    # Las barras no son opcionales: sustituyen al gráfico de Z-Score y son lo
    # único que permite al participante localizar SU resultado.
    orden = sorted(a["laboratorios"], key=lambda l: l["resultado"])
    fig, ax = plt.subplots(figsize=(7.0, 2.55))
    xs = np.arange(len(orden))
    ax.bar(xs, [l["resultado"] for l in orden], color=GRIS,
           edgecolor="#7a828f", linewidth=0.3)
    if ref.get("mediana") is not None:
        ax.axhline(ref["mediana"], color="#4a5568", linestyle="--", linewidth=1.2)
    ax.set_xticks(xs)
    ax.set_xticklabels([l["id"] for l in orden], rotation=90, fontsize=5.5)
    ax.set_ylabel(f"Resultado ({unidad})")
    ax.grid(axis="y", linewidth=0.5)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.set_title("Resultados ordenados de menor a mayor — sin clasificación "
                 "de desempeño", fontsize=6, color="#6c757d", loc="left", pad=3)
    fig.tight_layout()
    fig.savefig(destino_barras, format=_fmt(destino_barras), bbox_inches="tight")
    plt.close(fig)


def fig_estratos(d, destino):
    """Estratificación del desempeño global. El porcentaje solo no distingue
    una falla aislada de trece; el estrato sí."""
    estratos = d["desempeno_global"]["estratos"]
    fig, ax = plt.subplots(figsize=(6.6, 1.9))
    ys = np.arange(len(estratos))[::-1]
    ax.barh(ys, [e["laboratorios"] for e in estratos],
            color=[e["color"] for e in estratos], height=0.6)
    for y, e in zip(ys, estratos):
        ax.annotate(f"  {e['laboratorios']} lab. ({e['pct']}%)",
                    xy=(e["laboratorios"], y), va="center", fontsize=8,
                    color="#333")
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{e['nombre']}\n({e['descripcion']})" for e in estratos],
                       fontsize=7.5)
    ax.set_xlabel("Laboratorios")
    ax.set_xlim(0, max(e["laboratorios"] for e in estratos) * 1.35)
    ax.grid(axis="x", linewidth=0.5)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(destino, format=_fmt(destino), bbox_inches="tight")
    plt.close(fig)


def fig_heatmap(d, destino):
    """Mapa consolidado laboratorio × analito. El orden lexicográfico de los
    identificadores coincide con el numérico por el relleno a 3 dígitos."""
    lab_ids = sorted({l["id"] for a in d["analitos"] for l in a["laboratorios"]})
    analitos = d["analitos"]

    # Matriz de estado, no de z: en papel no hay tooltip que desambigüe, así
    # que el color debe ser categórico y la leyenda explícita.
    mapa = {"A": 0, "C": 1, "I": 2}
    M = np.full((len(analitos), len(lab_ids)), np.nan)
    for i, a in enumerate(analitos):
        por_id = {l["id"]: l for l in a["laboratorios"]}
        for j, lid in enumerate(lab_ids):
            l = por_id.get(lid)
            if l and l["clasificacion"] in mapa:
                M[i, j] = mapa[l["clasificacion"]]

    cmap = matplotlib.colors.ListedColormap([VERDE, AMARILLO, ROJO])
    cmap.set_bad("#e9ecef")

    alto = max(4.2, len(analitos) * 0.20 + 1.5)
    fig, ax = plt.subplots(figsize=(11.0, alto))
    ax.imshow(np.ma.masked_invalid(M), aspect="auto", cmap=cmap, vmin=-0.5,
              vmax=2.5, interpolation="nearest")

    ax.set_xticks(np.arange(len(lab_ids)))
    ax.set_xticklabels(lab_ids, rotation=90, fontsize=5.5)
    ax.set_yticks(np.arange(len(analitos)))
    ax.set_yticklabels(
        [a["nombre"] + (" (no evaluado)" if es_no_evaluado(a) else "")
         for a in analitos], fontsize=6.5)
    ax.set_xticks(np.arange(-.5, len(lab_ids), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(analitos), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.8)
    ax.tick_params(which="minor", length=0)

    ax.legend(handles=[
        Patch(facecolor=VERDE, label="Satisfactorio (|z| ≤ 2)"),
        Patch(facecolor=AMARILLO, label="Alerta (2 < |z| < 3)"),
        Patch(facecolor=ROJO, label="No satisfactorio (|z| ≥ 3)"),
        Patch(facecolor="#e9ecef", label="Sin evaluar / no reportó"),
    ], loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=4, fontsize=7,
        frameon=False)
    fig.tight_layout()
    fig.savefig(destino, format=_fmt(destino), bbox_inches="tight")
    plt.close(fig)


# ── Documento ─────────────────────────────────────────────────────────────

PREAMBULO = r"""\documentclass[11pt,letterpaper]{article}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[spanish,es-noshorthands]{babel}
\usepackage[letterpaper,margin=2.4cm,top=2.8cm,bottom=2.4cm]{geometry}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{tabularx}
\usepackage{ragged2e}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{tcolorbox}
\usepackage{pdflscape}
\usepackage{textcomp}
\usepackage{tocloft}
\usepackage[hidelinks]{hyperref}
\tcbuselibrary{skins,breakable}

\definecolor{uasdazul}{HTML}{003F87}
\definecolor{uasdoro}{HTML}{FDB913}
\definecolor{grisclaro}{HTML}{F4F6FB}
\definecolor{verdeok}{HTML}{1E7E34}
\definecolor{ambar}{HTML}{B8860B}
\definecolor{rojoalerta}{HTML}{C62828}

\setlength{\headheight}{22pt}
\addtolength{\topmargin}{-10pt}
\pagestyle{fancy}
\fancyhf{}
\lhead{\small\color{uasdazul}\textbf{CONCALAB-UASD}}
\rhead{\small\color{uasdazul}Informe __CODIGO__ \textemdash{} __AREA__}
\cfoot{\small\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\headrule}{\hbox to\headwidth{\color{uasdoro}\leaders\hrule height \headrulewidth\hfill}}

\titleformat{\section}{\color{uasdazul}\Large\bfseries}{\thesection}{0.6em}{}
\titleformat{\subsection}{\color{uasdazul}\large\bfseries}{\thesubsection}{0.6em}{}
\titleformat{\subsubsection}{\color{uasdazul}\normalsize\bfseries}{\thesubsubsection}{0.6em}{}
\setlist{itemsep=2pt,parsep=0pt,topsep=3pt}
\setlength{\parskip}{0.45em}
\setlength{\parindent}{0pt}
\renewcommand{\arraystretch}{1.15}

% Recuadro de nota / criterio. Se usa para lo que el proveedor DECLARA
% (criterios, decisiones, limitaciones), no para adorno.
\newtcolorbox{nota}[1][]{colback=grisclaro,colframe=uasdazul,boxrule=0.6pt,
  left=6pt,right=6pt,top=5pt,bottom=5pt,arc=2pt,breakable,#1}
\newtcolorbox{aviso}[1][]{colback=yellow!8,colframe=ambar,boxrule=0.6pt,
  left=6pt,right=6pt,top=5pt,bottom=5pt,arc=2pt,breakable,#1}
\newtcolorbox{neutro}[1][]{colback=black!4,colframe=black!35,boxrule=0.6pt,
  left=6pt,right=6pt,top=5pt,bottom=5pt,arc=2pt,breakable,#1}

\hypersetup{pdftitle={Informe de Ensayo de Aptitud __CODIGO__},
            pdfauthor={CONCALAB-UASD}}

\begin{document}
"""


def portada(d, cfg, meta):
    logo_uasd = RAIZ / "pic" / "Uasd.png"
    logo_badge = RAIZ / "pic" / "logo-badge.png"
    ronda = cfg.get("ronda_activa", {})
    return rf"""
\begin{{titlepage}}
\thispagestyle{{empty}}
\centering
\vspace*{{0.6cm}}

\includegraphics[height=3.1cm]{{{logo_uasd.as_posix()}}}
\hspace{{1.4cm}}
\includegraphics[height=3.1cm]{{{logo_badge.as_posix()}}}

\vspace{{0.9cm}}
{{\large\color{{uasdazul}}\textbf{{UNIVERSIDAD AUTÓNOMA DE SANTO DOMINGO}}}}\\[0.2cm]
{{\normalsize Primada de América \textemdash{{}} Fundada el 28 de octubre de 1538}}\\[0.5cm]
{{\Large\color{{uasdazul}}\textbf{{CONCALAB-UASD}}}}\\[0.15cm]
{{\normalsize Programa de Control de Calidad de Laboratorios}}

\vspace{{0.7cm}}
{{\color{{uasdoro}}\rule{{0.72\textwidth}}{{2pt}}}}

\vspace{{0.9cm}}
{{\Huge\color{{uasdazul}}\textbf{{Informe Final-Química Clínica}}}}\\[0.35cm]
{{\LARGE\color{{uasdazul}}Ensayo de Aptitud}}\\[0.7cm]
{{\Large\textbf{{{esc(meta['area_nombre'])}}}}}\\[0.35cm]
{{\Huge\color{{uasdoro}}\textbf{{{esc(d['codigo'])}}}}}\\[0.3cm]
{{\large {esc(ronda.get('descripcion', ''))}}}

\vspace{{0.9cm}}
{{\color{{uasdoro}}\rule{{0.72\textwidth}}{{2pt}}}}

\vspace{{0.8cm}}
\begin{{minipage}}{{0.82\textwidth}}\centering
{{\normalsize
\textbf{{{d['resumen']['laboratorios']}}} laboratorios participantes \quad\textbullet\quad
\textbf{{{len(d['analitos'])}}} analitos \quad\textbullet\quad
\textbf{{{d['resumen']['total']}}} resultados evaluados\\[0.5cm]
Evaluación por aptitud al uso según \textbf{{CLIA}} (Error Total Permitido, 42 CFR §493.931)\\
Valor asignado por media robusta \textemdash{{}} \textbf{{ISO 13528:2022}}, Algoritmo A\\
Elaborado conforme a las directrices de la \textbf{{ISO/IEC 17043}}
}}
\end{{minipage}}

\vfill
{{\normalsize\textbf{{Documento definitivo}} \quad\textbullet\quad Fecha de emisión: {esc(meta['fecha_larga'])}}}\\[0.2cm]
{{\small Santo Domingo, República Dominicana}}
\vspace{{0.6cm}}
\end{{titlepage}}
"""


def control_documento(d, meta, equipo):
    filas = "\n".join(
        rf"{esc(n)} & {esc(c)} \\" for n, c in equipo)
    return rf"""
\section*{{Control del documento}}
\addcontentsline{{toc}}{{section}}{{Control del documento}}

\begin{{tabularx}}{{\textwidth}}{{@{{}}>{{\bfseries\RaggedRight}}p{{5.0cm}}X@{{}}}}
\toprule
Código del ensayo & {esc(d['codigo'])} \\
Área evaluada & {esc(meta['area_nombre'])} \\
Proveedor del ensayo & CONCALAB-UASD, Universidad Autónoma de Santo Domingo \\
Tipo de documento & Informe final de ronda \textemdash{{}} \textbf{{definitivo}} \\
Fecha de cálculo y emisión & {esc(meta['fecha_larga'])} \\
Modelo de evaluación & Aptitud al uso (CLIA), $\sigma_{{pt}} = ET_a/3$ \\
Informe en línea & \url{{https://www.concalabuasd.com/publicaciones/informes/{esc(d['codigo'])}.html}} \\
\bottomrule
\end{{tabularx}}

\subsection*{{Equipo responsable}}
\begin{{tabularx}}{{\textwidth}}{{@{{}}Xp{{6.6cm}}@{{}}}}
\toprule
\textbf{{Nombre}} & \textbf{{Función}} \\
\midrule
{filas}
\bottomrule
\end{{tabularx}}

\vspace{{0.4em}}
{{\small Este informe fue elaborado, revisado y aprobado por el equipo indicado.
Las cifras que contiene proceden del mismo conjunto de datos y del mismo cálculo
que sustentan el informe publicado en el sitio web de CONCALAB-UASD.}}
"""


def seccion_concalab():
    return r"""
\section{CONCALAB-UASD: quiénes somos}

\textbf{CONCALAB-UASD} es el programa de Control de Calidad de Laboratorios de la
Universidad Autónoma de Santo Domingo, la Primada de América. Su finalidad es
\textbf{apoyar a los laboratorios clínicos nacionales} en la evaluación objetiva y
periódica de la calidad de sus resultados, mediante ensayos de aptitud
(evaluación externa de la calidad) diseñados y analizados con métodos
estadísticos internacionalmente reconocidos.

Un ensayo de aptitud permite a cada laboratorio comparar su desempeño frente al
de sus pares y frente a un criterio de aceptación clínicamente relevante, y
constituye una herramienta esencial de mejora continua. CONCALAB-UASD no ejerce
función fiscalizadora: los resultados individuales son \textbf{confidenciales} y se
publican bajo un identificador anónimo, de modo que el informe sea un instrumento
de mejora y no de sanción.

\begin{nota}
\textbf{Objetivos del programa}
\begin{itemize}
  \item Ofrecer a los laboratorios clínicos del país un ensayo de aptitud
        accesible, técnicamente sólido y con retroalimentación útil.
  \item Detectar desviaciones analíticas —sesgo, imprecisión, efectos de
        método— antes de que impacten al paciente.
  \item Generar evidencia objetiva de desempeño, utilizable en los procesos
        de acreditación y habilitación de los laboratorios participantes.
  \item Fortalecer la formación en gestión de la calidad desde la academia.
\end{itemize}
\end{nota}

\subsection{Marco normativo de referencia}

Este informe se elabora siguiendo las directrices de la \textbf{ISO/IEC 17043}
(requisitos generales para proveedores de ensayos de aptitud) y aplica los
métodos estadísticos de la \textbf{ISO 13528:2022}. Los criterios de aceptación por
analito provienen de \textbf{CLIA} (42 CFR §493.931).

"""


def seccion_alcance(d, cfg, meta):
    ronda = cfg.get("ronda_activa", {})
    r = d["resumen"]
    n_pares = sum(1 for a in d["analitos"] if es_pares(a))
    n_ne = sum(1 for a in d["analitos"] if es_no_evaluado(a))
    return rf"""
\section{{Alcance de la participación interlaboratorial}}

\begin{{tabularx}}{{\textwidth}}{{@{{}}>{{\bfseries\RaggedRight}}p{{6.2cm}}X@{{}}}}
\toprule
Ronda & {esc(ronda.get('descripcion', ''))} ({esc(d['codigo'])}) \\
Área & {esc(meta['area_nombre'])} \\
Laboratorios participantes & {r['laboratorios']} \\
Analitos incluidos & {len(d['analitos'])} \\
\quad evaluados de forma agrupada & {len(d['analitos']) - n_pares - n_ne} \\
\quad evaluados por grupo de pares & {n_pares} \\
\quad publicados sin calificación & {n_ne} \\
Resultados recibidos y procesados & {r['total']} \\
Apertura de la ronda & {esc(ronda.get('fecha_apertura', ''))} \\
Cierre de recepción de resultados & {esc(ronda.get('fecha_cierre', ''))} \\
Cálculo estadístico & {esc(d['fecha'])} \\
Emisión del informe & {esc(meta['fecha_larga'])} \\
Ámbito & Nacional (República Dominicana) \\
\bottomrule
\end{{tabularx}}

Cada laboratorio recibió el material de ensayo y reportó sus resultados a través
del portal de CONCALAB-UASD. El número de analitos reportados varía entre
laboratorios —según según su alcance de servicio—, por lo que todos los
porcentajes de conformidad individuales se expresan siempre acompañados del
número de analitos sobre el que se calculan.

\subsection{{Confidencialidad y anonimato}}

Los laboratorios participantes se identifican en este informe mediante un
\textbf{{identificador público}} de la forma \texttt{{L-NNN}}, asignado por CONCALAB-UASD
y declarado para esta ronda. Los nombres reales de los laboratorios, sus datos
de contacto, y el método e instrumento que emplea cada uno \textbf{{no se publican en
ningún documento ni archivo del informe}}.

Por la misma razón, los grupos de método se nombran por su química
(\emph{{química húmeda}}, \emph{{química seca}}) y \textbf{{nunca por el fabricante}}: con grupos
pequeños en un mercado local reducido, nombrar la marca permitiría reidentificar
laboratorios. La distinción entre química seca y húmeda es la causa real del
efecto de método observado, de modo que el informe conserva su poder explicativo
sin revelar la marca.
"""


def seccion_criterios(d):
    crit = d["criterios_aceptacion"]
    niveles = "\n".join(
        rf"{esc(n['clasificacion'])} & {esc(n['nombre'])} & {esc(n['regla'])} \\"
        for n in crit["niveles"])
    return rf"""
\section{{Criterios de evaluación de la conformidad}}
\label{{sec:criterios}}

\subsection{{Qué es CLIA y por qué se usa}}

{esc(crit['que_es_clia'])}

\subsection{{Valor asignado (X*)}}

{esc(crit['valor_asignado'])} El Algoritmo A es un estimador robusto: acota
iterativamente la influencia de los valores extremos, de modo que un resultado
groseramente desviado no arrastra el valor asignado del conjunto.

\subsection{{Dispersión (\texorpdfstring{{$\sigma^*$}}{{sigma*}}, CV)}}

{esc(crit['dispersion'])}

\subsection{{Desviación estándar para la evaluación de la aptitud
(\texorpdfstring{{$\sigma_{{pt}}$}}{{sigma-pt}})}}

\begin{{nota}}
El Error Total Permitido ($ET_a$) se convierte en desviación estándar de aptitud
mediante
\[
  \sigma_{{pt}} = \frac{{ET_a}}{{3}},
  \qquad\text{{de modo que}}\qquad
  z = \frac{{x_i - X^*}}{{\sigma_{{pt}}}}
\]
Por construcción, \textbf{{$|z| = 3$ equivale exactamente a una desviación igual al
Error Total Permitido}}, es decir, al límite de aceptación de CLIA §493.931. Es el
mismo criterio que emplea ESfEQA; el índice \emph{{PA}} de PROASECAL es este mismo
$z$ reescalado a porcentaje ($PA = z \times 33{{,}}33$).
\end{{nota}}

\textbf{{Por qué no se evalúa con la $\sigma^*$ de los participantes.}} Un $z$ calculado
con la desviación robusta del grupo mide \emph{{concordancia entre laboratorios}}, no
aptitud clínica: en un conjunto disperso la ventana de aceptación se ensancha y
casi nadie reprueba, aunque el resultado sea clínicamente inaceptable. El modelo
CLIA fija el criterio en un límite externo, independiente de lo bien o mal que
haya rendido el grupo. Ambos cálculos se realizaron; en este informe se reporta
el de CLIA.

\subsection{{Niveles de clasificación}}

\begin{{tabularx}}{{\textwidth}}{{@{{}}cp{{4.2cm}}X@{{}}}}
\toprule
\textbf{{Clave}} & \textbf{{Clasificación}} & \textbf{{Regla}} \\
\midrule
{niveles}
NE & Sin evaluar & Grupo de pares insuficiente, analito no evaluado, o
resultado no reportado \\
\bottomrule
\end{{tabularx}}

La clasificación se aplica sobre el \textbf{{$z$ redondeado}} a dos decimales, para que
el número mostrado y la clasificación coincidan en el borde: un $z$ de 2{{,}}998 se
muestra como 3{{,}}00 y clasifica como no satisfactorio.

\subsection{{Fuente del Error Total Permitido}}

{esc(crit['eta_fuente'])} El $ET_a$ de cada analito se declara en el Anexo A, con
su regla (\emph{{porcentaje}}, \emph{{valor absoluto}} o \emph{{el mayor de ambos}}) y su fuente.

\subsection{{Tratamiento de los datos previo al cálculo}}

\subsubsection*{{Los ceros se excluyen: son ausencia de medición, no medición}}

Algunos laboratorios escriben \texttt{{0}}, \texttt{{00}} o \texttt{{0.00}} para indicar
«no realizado». Estos valores se descartan antes de calcular. El criterio es
clínico: ningún analizador devuelve 0{{,}}00 de magnesio, HDL, CK o hierro en un
suero real. Tratarlos como medición causaría un daño doble: al laboratorio, que
recibiría una no conformidad falsa; y al resto de participantes, porque el cero
arrastra el valor asignado e infla la $\sigma^*$, escondiendo desviaciones reales.

\subsubsection*{{Auditoría de unidades}}

Antes de publicar se verifica, para cada resultado no conforme, si la desviación
se explica por una \textbf{{unidad de reporte distinta}} y no por desempeño analítico:
se calcula el factor $X^*/x_i$ y se contrasta contra las conversiones reales de
química clínica (mmol/L $\leftrightarrow$ mg/dL, µmol/L $\leftrightarrow$ mg/dL,
g/L $\leftrightarrow$ g/dL, y escalas $\times$10, $\times$100, $\times$1000).
Reportar como no conforme lo que en realidad es un error de unidad sería injusto
con el laboratorio, por eso la comprobación se ejecuta en todas las rondas.

\subsection{{Evaluación por grupo de pares (ISO 13528, §7)}}

Cuando dos plataformas analíticas no son comparables entre sí —típicamente
química seca frente a química húmeda—, agruparlas en un único valor asignado
penaliza a ambos grupos a la vez y, peor aún, infla la $\sigma^*$ hasta que nadie
reprueba: un «todo satisfactorio» que es un \textbf{{falso negativo}}. En esos casos cada
plataforma recibe su propio $X^*$ y su propio $\sigma^*$, y el $z$ se calcula dentro
del grupo que corresponde.

\begin{{nota}}
\textbf{{Un grupo con menos de 8 participantes no se evalúa.}} Esos laboratorios se
reportan como \textbf{{NE}} (sin evaluar), sin Z-Score, y no computan en los totales.
\textbf{{No se anexan al grupo más parecido}}: evaluar un laboratorio contra un método
que no es el suyo sería incorrecto. La decisión de qué analitos van por grupo de
pares se toma \textbf{{por ronda}}, se documenta con su justificación y se versiona
junto al informe; no es una constante heredada de rondas anteriores.
\end{{nota}}
"""


def seccion_decision_no_evaluado(d, cfg):
    dec = (cfg.get("decisiones_evaluacion", {}).get(d["codigo"], {})
           .get(d["area"], {}))
    sin_ev = dec.get("sin_evaluar", [])
    if not sin_ev:
        return ""
    just = dec.get("sin_evaluar_justificacion", "")
    nombres = ", ".join(esc(n) for n in sin_ev)
    return rf"""
\subsection{{Analito publicado sin calificación de desempeño}}
\label{{sec:no-evaluado}}

En esta ronda, CONCALAB-UASD decidió \textbf{{no emitir calificación de conformidad}}
para: \textbf{{{nombres}}}.

\begin{{neutro}}
\textbf{{Justificación de la decisión.}} {esc(just)}
\end{{neutro}}

Esta es una \textbf{{decisión de política del proveedor}}, no una consecuencia
automática de los datos, y por ello se declara y se documenta de forma expresa.
Sus consecuencias se aplican de manera completa y verificable: el analito se
publica \textbf{{sin valor asignado}} —publicar un $X^*$ mientras se declara que no hay
consenso defendible sería una contradicción—, todos sus resultados quedan como
\textbf{{NE}}, no computa en el desempeño global ni en el resumen por laboratorio, y su
gráfico se presenta \textbf{{sin banda de aceptación y sin Z-Score}}. Se publica una
referencia descriptiva (mediana y rango) rotulada como tal, para que cada
participante pueda ubicar su valor respecto al conjunto.
"""


def seccion_resultados_globales(d):
    r = d["resumen"]
    g = d["desempeno_global"]
    conc = g["concentracion"]

    # `resumen.total` es A+C+I: los NE NO están dentro. Los porcentajes se
    # calculan sobre esa base y por eso suman 100 exacto. Meter los NE en la
    # misma columna haría que la tabla sumara 104,9%, porque estaría dividiendo
    # entre una base que no los contiene. Un NE tampoco es un desempeño: es la
    # ausencia de evaluación, y promediarlo con los evaluados diluiría las tres
    # cifras que sí miden desempeño.
    pct = lambda x: f"{x / r['total'] * 100:.1f}".replace(".", ",")
    recibidos = r["total"] + r["sin_evaluar"]

    # Los NE tienen dos causas distintas y conviene separarlas: una es una
    # decisión de política sobre un analito entero, la otra un límite
    # estadístico que afecta a laboratorios sueltos.
    ne_analito, ne_grupo = 0, 0
    nombres_ne_analito, nombres_ne_grupo = [], []
    for a in d["analitos"]:
        n = a["conteos"]["NE"]
        if not n:
            continue
        if es_no_evaluado(a):
            ne_analito += n
            nombres_ne_analito.append(a["nombre"])
        else:
            ne_grupo += n
            nombres_ne_grupo.append(a["nombre"])

    filas_ne = []
    if ne_analito:
        filas_ne.append(
            rf"Analito publicado sin calificación ({', '.join(esc(x) for x in nombres_ne_analito)}) "
            rf"& {ne_analito} \\")
    if ne_grupo:
        filas_ne.append(
            rf"Grupo de pares insuficiente ($n < 8$: {', '.join(esc(x) for x in nombres_ne_grupo)}) "
            rf"& {ne_grupo} \\")

    excl = g.get("analitos_excluidos") or []
    nota_excl = ""
    if excl:
        nota_excl = (r"\emph{Excluye " + ", ".join(esc(e) for e in excl)
                     + r", analito publicado sin calificación de desempeño.}")
    return rf"""
\section{{Resultados globales de la ronda}}

\subsection{{Desempeño por resultado}}

De los {recibidos} resultados recibidos en la ronda, \textbf{{{r['total']}}} recibieron
calificación de desempeño. Los porcentajes de esta tabla se calculan sobre esos
{r['total']} y suman 100\,\%.

\begin{{tabularx}}{{\textwidth}}{{@{{}}Xrr@{{}}}}
\toprule
\textbf{{Clasificación}} & \textbf{{Resultados}} & \textbf{{\%}} \\
\midrule
\textcolor{{verdeok}}{{$\blacksquare$}}~Satisfactorio ($|z| \le 2$) & {r['aceptables']} & {pct(r['aceptables'])} \\
\textcolor{{ambar}}{{$\blacksquare$}}~Alerta ($2 < |z| < 3$) & {r['cuestionables']} & {pct(r['cuestionables'])} \\
\textcolor{{rojoalerta}}{{$\blacksquare$}}~No satisfactorio ($|z| \ge 3$) & {r['inaceptables']} & {pct(r['inaceptables'])} \\
\midrule
\textbf{{Total de resultados evaluados}} & \textbf{{{r['total']}}} & \textbf{{100,0}} \\
\bottomrule
\end{{tabularx}}

\subsubsection*{{Resultados sin evaluar (NE)}}

Los siguientes resultados \textbf{{no recibieron calificación}} y por eso \textbf{{no entran
en la tabla anterior}}: un NE no es un desempeño intermedio entre satisfactorio y
no satisfactorio, sino la ausencia de evaluación, e incluirlo en el
denominador diluiría las tres cifras que sí miden desempeño.

\begin{{tabularx}}{{\textwidth}}{{@{{}}Xr@{{}}}}
\toprule
\textbf{{Motivo}} & \textbf{{Resultados}} \\
\midrule
{chr(10).join(filas_ne)}
\midrule
\textbf{{Total sin evaluar}} & \textbf{{{r['sin_evaluar']}}} \\
\midrule
\textbf{{Total de resultados recibidos}} ({r['total']} evaluados + {r['sin_evaluar']} sin evaluar)
& \textbf{{{recibidos}}} \\
\bottomrule
\end{{tabularx}}

\subsection{{Desempeño por laboratorio}}

La cifra anterior mide \emph{{resultados}}. La que sigue mide \textbf{{laboratorios}}, y es la
que debe leerse como titular de la ronda:

\begin{{nota}}
\textbf{{Criterio.}} {esc(g['criterio'])}

\vspace{{0.4em}}
\textbf{{{g['conformes']} de {g['laboratorios']} laboratorios ({str(g['pct_conformes']).replace('.', ',')}\%)}}
no presentaron ninguna no conformidad en esta ronda. {nota_excl}
\end{{nota}}

La distancia entre este porcentaje y el de resultados satisfactorios es el punto:
un resultado errado que llega a un paciente es una falla, sin importar cuántos
otros salieron bien.

\begin{{center}}
\includegraphics[width=0.92\textwidth]{{figs/estratos.pdf}}
\end{{center}}

\begin{{aviso}}
\textbf{{Las no conformidades no están repartidas de manera uniforme, pero
tampoco se limitan a unos pocos laboratorios.}}
{conc['laboratorios']} laboratorios concentran {conc['no_conformes']} de los
{conc['no_conformes_total']} resultados no satisfactorios de la ronda
({str(conc['pct']).replace('.', ',')}\%), de modo que el esfuerzo de mejora rinde
más si empieza por ese subconjunto. Aun así, el resto de las no conformidades se
reparte entre la mayoría de los participantes: la estratificación anterior
muestra que el hallazgo alcanza al conjunto del programa y no puede tratarse
como un problema de unos pocos.
\end{{aviso}}
"""


def tabla_laboratorios(d):
    filas = []
    estratos = d["desempeno_global"]["estratos"]

    def estrato_de(nc):
        for e in estratos:
            if nc >= e["desde"] and (e["hasta"] is None or nc <= e["hasta"]):
                return e
        return estratos[-1]

    col = {"satisfactorio": "verdeok", "atencion": "ambar",
           "correctiva": "rojoalerta"}
    for row in sorted(d["desempeno_global"]["por_laboratorio"],
                      key=lambda r: (-r["pct_conformidad"], -r["n"], r["id"])):
        e = estrato_de(row["I"])
        c = col.get(e["clave"], "black")
        filas.append(
            rf"\texttt{{{esc(row['id'])}}} & {row['n']} & {row['A']} & {row['C']} "
            rf"& {row['I']} & {str(row['pct_conformidad']).replace('.', ',')}\% "
            rf"& \textcolor{{{c}}}{{{esc(e['nombre'])}}} \\")
    cuerpo = "\n".join(filas)
    return rf"""
\subsection{{Consolidado por laboratorio}}

La columna \textbf{{\% dentro}} es la proporción de resultados del laboratorio que
quedaron \textbf{{dentro del criterio de aceptación}}, es decir con $|z| < 3$: suma los
satisfactorios y las alertas, porque una alerta está dentro del Error Total
Permitido y no constituye un incumplimiento. Se calcula sobre \textbf{{el alcance del
propio laboratorio}} —los analitos que reportó y se le evaluaron, entre 9 y 25 en
esta ronda— y por eso se acompaña siempre de esa $n$: un 100\,\% sobre 9 analitos
no equivale a un 100\,\% sobre 24. Los analitos sin evaluar no entran ni en el
numerador ni en el denominador.

\begin{{small}}
\begin{{longtable}}{{@{{}}lrrrrrl@{{}}}}
\toprule
\textbf{{Lab.}} & \textbf{{n}} & \textbf{{Satisf.}} & \textbf{{Alerta}} &
\textbf{{No satisf.}} & \textbf{{\% dentro}} & \textbf{{Estrato}} \\
\midrule
\endfirsthead
\toprule
\textbf{{Lab.}} & \textbf{{n}} & \textbf{{Satisf.}} & \textbf{{Alerta}} &
\textbf{{No satisf.}} & \textbf{{\% dentro}} & \textbf{{Estrato}} \\
\midrule
\endhead
\bottomrule
\endfoot
{cuerpo}
\end{{longtable}}
\end{{small}}
"""


def tabla_analitos(d):
    filas = []
    for a in d["analitos"]:
        c = a["conteos"]
        if es_no_evaluado(a):
            ref = a.get("referencia_descriptiva", {})
            xa = rf"\emph{{med. {ref.get('mediana', '')}}}"
            sd = cv = eta = "---"
        elif es_pares(a):
            xa = r"\emph{por grupo}"
            sd = cv = r"\emph{por grupo}"
            g0 = next((g for g in a["grupos"] if g["evaluado"]), None)
            eta = eta_label(g0.get("eta") if g0 else None, a["unidad"])
        else:
            xa = str(a["valor_asignado"])
            sd = str(a["sd_robusta"])
            cv = f"{str(a['cv']).replace('.', ',')}\\%"
            eta = eta_label(a.get("eta"), a["unidad"])
        filas.append(
            rf"{esc(a['nombre'])} & {esc(a['unidad'])} & {a['n']} & {xa} & {sd} "
            rf"& {cv} & {eta} & {c['A']} & {c['C']} & {c['I']} & {c['NE']} \\")
    cuerpo = "\n".join(filas)
    return rf"""


\begin{{landscape}}
\subsection{{Resumen por analito}}
\begin{{footnotesize}}
\begin{{longtable}}{{@{{}}llrrrrlrrrr@{{}}}}
\toprule
\textbf{{Analito}} & \textbf{{Unidad}} & \textbf{{n}} & \textbf{{$X^*$}} &
\textbf{{$\sigma^*$}} & \textbf{{CV}} & \textbf{{$ET_a$}} &
\textbf{{Sat.}} & \textbf{{Alerta}} & \textbf{{No sat.}} & \textbf{{NE}} \\
\midrule
\endfirsthead
\toprule
\textbf{{Analito}} & \textbf{{Unidad}} & \textbf{{n}} & \textbf{{$X^*$}} &
\textbf{{$\sigma^*$}} & \textbf{{CV}} & \textbf{{$ET_a$}} &
\textbf{{Sat.}} & \textbf{{Alerta}} & \textbf{{No sat.}} & \textbf{{NE}} \\
\midrule
\endhead
\bottomrule
\endfoot
{cuerpo}
\end{{longtable}}
\end{{footnotesize}}
\end{{landscape}}
"""


def tabla_consolidado_analito(d):
    """Los mismos conteos que la tabla anterior, girados: qué analitos costaron
    más a la red de laboratorios. La tabla anterior está en orden de informe y
    responde «cómo salió este analito»; esta responde «cuáles fueron los
    difíciles», que es una pregunta distinta y no se contesta leyendo 26 filas
    en otro orden."""
    evaluados = [a for a in d["analitos"] if not es_no_evaluado(a)]
    sin = [a for a in d["analitos"] if es_no_evaluado(a)]

    filas = []
    for a in sorted(evaluados, key=lambda a: -a["conteos"]["pct_dentro"]):
        c = a["conteos"]
        n = c["A"] + c["C"] + c["I"]
        filas.append(
            rf"{esc(a['nombre'])} & {n} & {c['A']} & {c['C']} & {c['I']} & {c['NE']} "
            rf"& {str(c['pct_dentro']).replace('.', ',')}\% \\")
    for a in sin:
        # Sin calificación de desempeño: no tiene % que ordenar, pero omitirlo
        # de la tabla lo haría desaparecer del informe sin explicación.
        filas.append(rf"{esc(a['nombre'])} & --- & --- & --- & --- "
                     rf"& {a['conteos']['NE']} & \emph{{no evaluado}} \\")
    cuerpo = "\n".join(filas)
    return rf"""
\subsection{{Consolidado por analito}}

La misma información de la tabla anterior ordenada por \textbf{{\% dentro}} —de mayor
a menor— para mostrar en qué analitos se concentró la dificultad de la ronda. El
porcentaje se calcula igual que en el consolidado por laboratorio: los
satisfactorios más las alertas sobre los resultados evaluados, porque una alerta
está dentro del Error Total Permitido. Los resultados sin evaluar (NE) se muestran
aparte y no entran en el cálculo.

Un \% dentro bajo no señala a un laboratorio en particular: indica un analito en el
que buena parte de la red se apartó del $ET_a$, y es donde una acción de mejora
alcanza a más participantes a la vez.

\begin{{small}}
\begin{{longtable}}{{@{{}}lrrrrrr@{{}}}}
\toprule
\textbf{{Analito}} & \textbf{{n eval.}} & \textbf{{Satisf.}} & \textbf{{Alerta}} &
\textbf{{No satisf.}} & \textbf{{NE}} & \textbf{{\% dentro}} \\
\midrule
\endfirsthead
\toprule
\textbf{{Analito}} & \textbf{{n eval.}} & \textbf{{Satisf.}} & \textbf{{Alerta}} &
\textbf{{No satisf.}} & \textbf{{NE}} & \textbf{{\% dentro}} \\
\midrule
\endhead
\bottomrule
\endfoot
{cuerpo}
\end{{longtable}}
\end{{small}}
"""


def ficha_analito(a, i):
    """Bloque por analito: encabezado, estadísticas, aviso y las dos gráficas
    —el mismo contenido que la sección correspondiente del informe web."""
    c = a["conteos"]
    etiqueta = ""
    if es_pares(a):
        etiqueta = r"\;{\small\color{uasdazul}[grupo de pares]}"
    if es_no_evaluado(a):
        etiqueta = r"\;{\small\color{black!55}[no evaluado]}"

    if es_no_evaluado(a):
        ref = a.get("referencia_descriptiva", {})
        stats = rf"""
\begin{{tabularx}}{{\textwidth}}{{@{{}}>{{\bfseries\RaggedRight}}p{{5.2cm}}X@{{}}}}
\toprule
Laboratorios (n) & {a['n']} \\
Mediana & {ref.get('mediana', '')} {esc(a['unidad'])} \emph{{(referencia descriptiva, no valor asignado)}} \\
Rango observado & {ref.get('minimo', '')} \textendash{{}} {ref.get('maximo', '')} {esc(a['unidad'])} \\
Calificación de desempeño & \textbf{{No se emite}} \\
\bottomrule
\end{{tabularx}}
"""
        aviso = (r"\begin{neutro}" + desmarcar(a.get("nota_sin_evaluar"))
                 + r"\end{neutro}")
    elif es_pares(a):
        gr = []
        for g in a["grupos"]:
            if g["evaluado"]:
                nota_n = (r" \emph{(n < 12; ver limitaciones)}"
                          if g.get("n_suficiente") is False else "")
                gr.append(
                    rf"{esc(g['nombre'])} & n = {g['n']} · $X^*$ = {g['valor_asignado']} "
                    rf"{esc(a['unidad'])} · $\sigma^*$ = {g['sd_robusta']} · "
                    rf"CV = {str(g['cv']).replace('.', ',')}\% · "
                    rf"$ET_a$ {eta_label(g.get('eta'), a['unidad'])}{nota_n} \\")
            else:
                gr.append(rf"{esc(g['nombre'])} & n = {g['n']} · "
                          rf"\textbf{{sin evaluar}} \textemdash{{}} "
                          rf"{esc(g.get('motivo', ''))} \\")
        stats = rf"""
\begin{{tabularx}}{{\textwidth}}{{@{{}}>{{\bfseries\RaggedRight}}p{{5.2cm}}X@{{}}}}
\toprule
Laboratorios (n) & {a['n']} \\
\midrule
{chr(10).join(gr)}
\midrule
Clasificaciones & \textcolor{{verdeok}}{{{plural(c['A'], 'satisfactorio', 'satisfactorios')}}} ·
\textcolor{{ambar}}{{{plural(c['C'], 'alerta', 'alertas')}}} ·
\textcolor{{rojoalerta}}{{{plural(c['I'], 'no satisfactorio', 'no satisfactorios')}}} · {c['NE']} sin evaluar \\
\bottomrule
\end{{tabularx}}
"""
        aviso = (r"\begin{aviso}\textbf{Evaluación por grupo de pares "
                 r"(ISO 13528, §7).} Este analito presenta un efecto de método "
                 r"entre plataformas analíticas: cada grupo recibe su propio "
                 r"valor asignado y el Z-Score se calcula dentro del grupo que "
                 r"corresponde. Los grupos que no alcanzan el mínimo de 8 "
                 r"participantes se reportan sin evaluar.\end{aviso}")
    else:
        stats = rf"""
\begin{{tabularx}}{{\textwidth}}{{@{{}}>{{\bfseries\RaggedRight}}p{{5.2cm}}X@{{}}}}
\toprule
Laboratorios (n) & {a['n']} \\
Valor asignado ($X^*$) & {a['valor_asignado']} {esc(a['unidad'])} \\
Desviación robusta ($\sigma^*$) & {a['sd_robusta']} {esc(a['unidad'])} \\
Coeficiente de variación & {str(a['cv']).replace('.', ',')}\% \\
Error Total Permitido ($ET_a$) & {eta_label(a.get('eta'), a['unidad'])} \\
Desv. de aptitud ($\sigma_{{pt}} = ET_a/3$) & {a['sigma_pt']:.3f} {esc(a['unidad'])} \\
Clasificaciones & \textcolor{{verdeok}}{{{plural(c['A'], 'satisfactorio', 'satisfactorios')}}} ·
\textcolor{{ambar}}{{{plural(c['C'], 'alerta', 'alertas')}}} ·
\textcolor{{rojoalerta}}{{{plural(c['I'], 'no satisfactorio', 'no satisfactorios')}}} \\
\bottomrule
\end{{tabularx}}
"""
        aviso = ""
        if a["cv"] > 30:
            aviso = (rf"\begin{{aviso}}\textbf{{CV = "
                     rf"{str(a['cv']).replace('.', ',')}\% (muy alto).}} La alta "
                     r"dispersión entre participantes sugiere diferencias "
                     r"relevantes de metodología, calibración o condiciones "
                     r"preanalíticas. Nótese que la dispersión es informativa: "
                     r"no interviene en la evaluación, que se hace contra el "
                     r"$ET_a$.\end{aviso}")
        elif a["cv"] > 15:
            aviso = (rf"\begin{{aviso}}\textbf{{CV = "
                     rf"{str(a['cv']).replace('.', ',')}\% (alto).}} La dispersión "
                     r"elevada puede indicar diferencias de metodología o "
                     r"calibración entre laboratorios. No interviene en la "
                     r"evaluación.\end{aviso}")

    if es_no_evaluado(a):
        pie = (r"{\small\emph{Arriba: distribución de los resultados, sin banda "
               r"de aceptación ni valor asignado. Abajo: resultado de cada "
               r"laboratorio, ordenado de menor a mayor. No se dibuja Z-Score "
               r"porque no se emite clasificación.}}")
    elif es_pares(a):
        pie = (r"{\small\emph{Arriba: distribución de resultados por grupo de "
               r"pares; cada línea discontinua es el valor asignado de su "
               r"grupo. No se dibuja una banda de aceptación única porque cada "
               r"grupo tiene la suya. Abajo: Z-Score de cada laboratorio, "
               r"calculado dentro de su grupo y ordenado de menor a mayor; las "
               r"líneas marcan $|z| = 2$ y $|z| = 3$.}}")
    else:
        pie = (r"{\small\emph{Arriba: distribución de resultados; la franja "
               r"verde es la banda de aceptación $X^* \pm ET_a$ y la línea "
               r"discontinua el valor asignado. Abajo: Z-Score de cada "
               r"laboratorio, ordenado de menor a mayor; las líneas marcan "
               r"$|z| = 2$ y $|z| = 3$.}}")

    return rf"""
\clearpage
\subsection[{esc(a['nombre'])}]{{{esc(a['nombre'])}{etiqueta}}}
\label{{ana:{slug(a['nombre'])}}}

{stats}

{aviso}

\begin{{center}}
\includegraphics[width=0.97\textwidth]{{figs/hist-{i}.pdf}}

\vspace{{0.3em}}
\includegraphics[width=0.97\textwidth]{{figs/bar-{i}.pdf}}
\end{{center}}

{pie}
"""


def seccion_limitaciones(d, cfg):
    dec = (cfg.get("decisiones_evaluacion", {}).get(d["codigo"], {})
           .get(d["area"], {}))
    pares = dec.get("grupo_pares", [])
    lista = ", ".join(esc(p) for p in pares) if pares else "---"
    return rf"""
\clearpage
\section{{Limitaciones declaradas}}

CONCALAB-UASD declara de forma expresa las limitaciones de esta ronda. Omitirlas
haría que las cifras se leyeran con más certeza de la que soportan.

\begin{{enumerate}}
\item \textbf{{Tamaño de algunos grupos de pares.}} En los analitos evaluados por
grupo de pares ({lista}), los grupos de química seca quedaron con $n = 8$
participantes, por debajo del $n \ge 12$ que recomienda la ISO 13528 para
estimar un valor asignado por consenso. Los resultados de esos grupos deben
interpretarse con esa reserva. Los grupos con $n < 8$ no se evaluaron.

\item \textbf{{Dispersión interlaboratorial elevada en varios analitos.}} Varios
analitos presentan un CV entre participantes superior al 20\,\%. Esa dispersión
no afecta la evaluación —que se hace contra el $ET_a$ y no contra el consenso—,
pero sí indica que el valor asignado por consenso tiene una incertidumbre mayor
de la deseable en esos analitos.

\item \textbf{{Una sola concentración por analito.}} La ronda evalúa un único nivel
de concentración, por lo que el desempeño observado no puede extrapolarse a todo
el intervalo de medición del laboratorio.

\item \textbf{{No comparabilidad con rondas anteriores a nivel de laboratorio.}} El
identificador público cambió respecto a la ronda EA-001-2025, que conserva el
suyo por trazabilidad de lo ya entregado. En consecuencia, los archivos públicos
de ambas rondas no permiten seguir a un mismo laboratorio de una a otra.

\end{{enumerate}}
"""


def seccion_conclusiones(d):
    g = d["desempeno_global"]
    r = d["resumen"]
    conc = g["concentracion"]
    estr = {e["clave"]: e for e in g["estratos"]}
    correctiva = estr.get("correctiva", {})
    atencion = estr.get("atencion", {})
    pct_sat = f"{r['aceptables'] / r['total'] * 100:.1f}".replace(".", ",")
    return rf"""
\clearpage
\section{{Conclusiones}}

\begin{{enumerate}}
\item \textbf{{Evaluados contra el criterio de aptitud clínica de CLIA, los
resultados de la ronda muestran un margen amplio de mejora.}} El
{pct_sat}\,\% de los resultados individuales fue satisfactorio, pero solo
\textbf{{{g['conformes']} de {g['laboratorios']} laboratorios
({str(g['pct_conformes']).replace('.', ',')}\%)}} completó la ronda sin ninguna no
conformidad. La segunda cifra es la relevante desde la perspectiva del paciente:
basta un resultado erróneo para comprometer una decisión clínica.

\item \textbf{{El hallazgo alcanza al conjunto del programa, con un subconjunto
que concentra una parte desproporcionada.}}
{correctiva.get('laboratorios', 0)} de {g['laboratorios']} laboratorios
({str(correctiva.get('pct', 0)).replace('.', ',')}\,\%) quedaron en el estrato de
acción correctiva, de modo que la mejora requiere acción del conjunto y no de
unos pocos. Dentro de ese cuadro, {conc['laboratorios']} laboratorios acumulan el
{str(conc['pct']).replace('.', ',')}\,\% de los resultados no satisfactorios: es
donde el esfuerzo rinde más al empezar, no el único lugar donde hace falta.

\item \textbf{{Se confirmó un efecto de método entre plataformas de química seca y
húmeda}} en varios analitos. Evaluarlos agrupados producía un falso negativo —una
$\sigma^*$ inflada en la que prácticamente nadie reprobaba—; la evaluación por
grupo de pares hizo aparecer las no conformidades reales y redujo el CV interno
de cada grupo a valores del orden del 10\,\%.

\item \textbf{{Un analito se publicó sin calificación de desempeño}} porque la
dispersión de los resultados entre los laboratorios participantes no permitió
establecer un valor asignado por consenso defendible, ni evaluando el conjunto
ni separando por grupo de pares. La decisión se apoya en lo observado en los
resultados reportados y \textbf{{no atribuye la causa al material de ensayo}}.
Retirarlo no alteró el desempeño global de la ronda: únicamente eliminó
calificaciones que la estadística de la ronda no podía sostener.

\item \textbf{{Ninguna no conformidad se explicó por error de unidad de reporte.}}
La auditoría de unidades verificó todos los resultados no conformes; las
desviaciones observadas son analíticas.
\end{{enumerate}}

\section{{Recomendaciones}}

\subsection*{{A los laboratorios participantes}}

\begin{{itemize}}
\item \textbf{{Estrato «Acción correctiva» ({correctiva.get('laboratorios', 0)}
laboratorios, {str(correctiva.get('pct', 0)).replace('.', ',')}\%)}} — abrir una
no conformidad formal en el sistema de calidad, investigar la causa raíz por
analito (calibración, control interno, mantenimiento, transporte y conservación
del material, transcripción del resultado) y documentar la acción tomada y su
verificación de eficacia.
\item \textbf{{Estrato «Requiere atención» ({atencion.get('laboratorios', 0)}
laboratorios, {str(atencion.get('pct', 0)).replace('.', ',')}\%)}} — revisar
específicamente los analitos no conformes y verificar la calibración y el
control interno de ese ensayo.
\item \textbf{{Todos}} — localizar el propio identificador en el mapa consolidado y
en los gráficos por analito; un patrón de $z$ del mismo signo en varios analitos
apunta a sesgo sistemático (calibración o trazabilidad) más que a imprecisión.
\item Conservar este informe como evidencia objetiva de evaluación externa de la
calidad para los procesos de habilitación y acreditación.
\end{{itemize}}


"""


def anexo_eta(cfg, d):
    especs = cfg["especificaciones_desempeno"][d["area"]]
    filas = []
    for nombre in sorted(especs, key=lambda s: s.lower()):
        e = especs[nombre]
        reglas = []
        if e.get("pct") is not None:
            reglas.append(f"±{e['pct']}\\%")
        if e.get("abs") is not None:
            reglas.append(f"±{e['abs']} {esc(e.get('unidad', ''))}")
        regla = (" o " if e.get("regla") == "mayor" else " ").join(reglas)
        crit = "el mayor de ambos" if e.get("regla") == "mayor" else "---"
        filas.append(rf"{esc(nombre)} & {regla} & {crit} & {esc(e.get('fuente', ''))} \\")
    return rf"""
\clearpage
\appendix
\renewcommand{{\thesection}}{{Anexo \Alph{{section}}}}
\addtocontents{{toc}}{{\protect\setlength{{\protect\cftsecnumwidth}}{{5.2em}}}}
\section{{Error Total Permitido por analito}}

Especificaciones de desempeño empleadas para calcular $\sigma_{{pt}} = ET_a/3$.
Cuando la regla es \emph{{el mayor de ambos}}, se aplica el criterio de CLIA: se toma
el mayor entre el porcentaje del valor asignado y el valor absoluto, lo que evita
que a concentraciones bajas el límite se vuelva impracticablemente estrecho.

\begin{{small}}
\begin{{longtable}}{{@{{}}lllp{{4.4cm}}@{{}}}}
\toprule
\textbf{{Analito}} & \textbf{{$ET_a$}} & \textbf{{Regla}} & \textbf{{Fuente}} \\
\midrule
\endfirsthead
\toprule
\textbf{{Analito}} & \textbf{{$ET_a$}} & \textbf{{Regla}} & \textbf{{Fuente}} \\
\midrule
\endhead
\bottomrule
\endfoot
{chr(10).join(filas)}
\end{{longtable}}
\end{{small}}

\emph{{CLIA no regula Lipasa ni Bilirrubina Directa; para esos analitos se emplea el
$ET_a$ deseable derivado de variación biológica (EFLM).}}
"""


def anexo_referencias():
    return r"""
\section{Referencias normativas}

\begin{itemize}
\item \textbf{ISO 13528:2022} — \emph{Statistical methods for use in proficiency
testing by interlaboratory comparison}. Algoritmo A (Anexo C) para el valor
asignado y la desviación robusta; §7 para la evaluación por grupo de pares.
\item \textbf{ISO/IEC 17043} — \emph{Conformity assessment. General requirements
for the competence of proficiency testing providers}. Estructura y contenido del
informe de resultados.
\item \textbf{CLIA} — \emph{Clinical Laboratory Improvement Amendments of 1988},
42 CFR §493.931. Criterios de desempeño aceptable por analito. Regla final
CMS-3355-F, \emph{Federal Register}, 11 de julio de 2022, y su corrección de
noviembre de 2022.
\item \textbf{EFLM} — \emph{Biological Variation Database}. Especificaciones de
desempeño deseables para los analitos no regulados por CLIA.
\end{itemize}
"""


def heatmap_seccion():
    return r"""
\clearpage
\begin{landscape}
\section{Mapa consolidado: laboratorio \texorpdfstring{$\times$}{x} analito}

Cada celda representa la clasificación de un laboratorio en un analito. Las
celdas grises corresponden a resultados sin evaluar —laboratorio que no reportó
el analito, grupo de pares insuficiente, o analito publicado sin calificación—.
Una fila mayoritariamente roja señala un analito problemático para el conjunto;
una columna mayoritariamente roja, un laboratorio que requiere acción correctiva
transversal.

\begin{center}
\includegraphics[width=\linewidth,height=0.80\textheight,keepaspectratio]{figs/heatmap.pdf}
\end{center}
\end{landscape}
"""


# ── Orquestación ──────────────────────────────────────────────────────────


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

AREAS = {"quimica": "Química Clínica", "uroanalisis": "Uroanálisis"}


SIGLAS = {"CONCALAB", "UASD", "CONCALAB-UASD"}
MINUSCULAS = {"de", "del", "la", "las", "el", "los", "y", "en", "a"}


def titulo_humano(t):
    """Capitaliza respetando las siglas y las preposiciones. `str.title()`
    convertiría CONCALAB en «Concalab» y «Gestión de Calidad» en
    «Gestión De Calidad», que en la página de firmas se nota."""
    palabras = t.split()
    salida = []
    for i, w in enumerate(palabras):
        if w.upper() in SIGLAS:
            salida.append(w.upper())
        elif i > 0 and w.lower() in MINUSCULAS:
            salida.append(w.lower())
        else:
            salida.append(w.capitalize())
    return " ".join(salida)


def leer_equipo():
    ruta = RAIZ / "prompts" / "equipo.md"
    equipo = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if "-" in linea:
            nombre, _, cargo = linea.partition("-")
            equipo.append((titulo_humano(nombre.strip()),
                           titulo_humano(cargo.strip())))
    return equipo


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codigo")
    ap.add_argument("--area", default="quimica")
    ap.add_argument("--solo-tex", action="store_true",
                    help="genera figuras y .tex sin compilar")
    args = ap.parse_args()

    cfg = json.loads((RAIZ / "data" / "config.json").read_text(encoding="utf-8"))
    codigo = args.codigo or cfg["ronda_activa"]["codigo"]

    ruta_json = RAIZ / "data" / "informes" / f"{codigo}-{args.area}-clia.json"
    if not ruta_json.exists():
        sys.exit(f"No existe {ruta_json}. Corra primero scripts/evaluar_clia.py.")
    d = json.loads(ruta_json.read_text(encoding="utf-8"))

    if d.get("modelo") != "clia":
        sys.exit("El JSON no declara modelo 'clia'. Este informe reporta CLIA.")

    build = RAIZ / "support" / f"pdf_{codigo}"
    figs = build / "figs"
    figs.mkdir(parents=True, exist_ok=True)

    y, m, day = (int(x) for x in d["fecha"].split("-"))
    meta = {
        "area_nombre": AREAS.get(args.area, args.area.title()),
        "fecha_larga": f"{day} de {MESES[m - 1]} de {y}",
    }

    print(f"→ Figuras ({len(d['analitos'])} analitos)…")
    fig_estratos(d, figs / "estratos.pdf")
    fig_heatmap(d, figs / "heatmap.pdf")
    for i, a in enumerate(d["analitos"]):
        if es_no_evaluado(a):
            fig_no_evaluado(a, figs / f"hist-{i}.pdf", figs / f"bar-{i}.pdf")
        else:
            fig_histograma(a, figs / f"hist-{i}.pdf")
            fig_zscore(a, figs / f"bar-{i}.pdf")
        print(f"   · {a['nombre']}")

    print("→ Documento LaTeX…")
    partes = [
        PREAMBULO.replace("__CODIGO__", esc(codigo))
                 .replace("__AREA__", esc(meta["area_nombre"])),
        portada(d, cfg, meta),
        r"\tableofcontents" + "\n" + r"\clearpage",
        control_documento(d, meta, leer_equipo()),
        r"\clearpage",
        seccion_concalab().replace(r"\end{aviso}", r"\end{aviso}"),
        seccion_alcance(d, cfg, meta),
        r"\clearpage",
        seccion_criterios(d),
        seccion_decision_no_evaluado(d, cfg),
        r"\clearpage",
        seccion_resultados_globales(d),
        tabla_laboratorios(d),
        tabla_analitos(d),
        tabla_consolidado_analito(d),
        r"\clearpage" + "\n" + r"\section{Resultados por analito}" + "\n"
        + "Cada analito se presenta con sus estadísticas de la ronda, la "
          "distribución de los resultados y el Z-Score de cada laboratorio. "
          "Los identificadores corresponden al identificador público de esta "
          "ronda.",
        *[ficha_analito(a, i) for i, a in enumerate(d["analitos"])],
        heatmap_seccion(),
        seccion_limitaciones(d, cfg),
        seccion_conclusiones(d),
        anexo_eta(cfg, d),
        anexo_referencias(),
        r"\end{document}",
    ]
    tex = build / f"informe_{codigo}.tex"
    # fsync antes de compilar: pdflatex es OTRO proceso y, si el .tex recién
    # escrito no está materializado en disco, lee un archivo a medias. El fallo
    # no aparece al leerlo —TeX no se queja del .tex— sino mucho después, al
    # releer su propio .aux al cerrar el documento, con un "Text line contains
    # an invalid character" que apunta al auxiliar y no a la causa. Compilar el
    # mismo .tex a mano funciona siempre, porque para entonces ya está en disco:
    # por eso el error solo se ve desde el script y parece no determinista.
    with open(tex, "w", encoding="utf-8") as f:
        f.write("\n".join(partes))
        f.flush()
        os.fsync(f.fileno())
    print(f"   {tex.relative_to(RAIZ)}")

    if args.solo_tex:
        return

    print("→ Compilando (pdflatex ×2)…")
    # Una corrida interrumpida deja .toc/.aux truncados (con bytes nulos), y
    # pdflatex aborta al leerlos en la corrida siguiente con un error que
    # apunta al auxiliar y no a la causa. Se borran siempre: son derivados.
    for aux in ("aux", "toc", "out", "lof", "lot"):
        (build / f"informe_{codigo}.{aux}").unlink(missing_ok=True)

    for pasada in (1, 2):
        p = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
             tex.name],
            cwd=build, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        if p.returncode != 0:
            cola = "\n".join(p.stdout.splitlines()[-40:])
            sys.exit(f"pdflatex falló en la pasada {pasada}:\n{cola}")

    destino = RAIZ / "publicaciones" / "informes" / f"{codigo}-informe.pdf"
    shutil.copy(build / f"informe_{codigo}.pdf", destino)
    # El .log de LaTeX es la fuente fiable del conteo: el PDF va comprimido
    # y sus objetos /Page no son legibles como texto plano.
    log = (build / f"informe_{codigo}.log").read_text(encoding="utf-8",
                                                      errors="replace")
    m = re.search(r"Output written on .*?\((\d+) pages?", log)
    paginas = m.group(1) if m else "?"
    print(f"\n✓ {destino.relative_to(RAIZ)}  ({paginas} páginas, "
          f"{destino.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
