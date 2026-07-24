"""
Informe preliminar de triaje — uso interno CONCALAB.

Calcula el Z-Score AGRUPADO por analito (todos los laboratorios juntos, sin
separar por instrumento) y genera un HTML de trabajo para responder dos
preguntas antes de armar el informe público:

  1. ¿En qué analitos está bien el grupo y en cuáles no?
  2. ¿Qué laboratorios y qué resultados concretos son atípicos, y con qué
     equipo y método los produjeron?

NO es el informe público. Se guarda en support/ y NO se commitea porque incluye
método e instrumento en texto libre, que permiten re-identificar laboratorios
(misma razón que support/ensayos_*.csv; ver CLAUDE.md).

Marca automáticamente los analitos donde la evaluación agrupada NO es confiable
porque conviven dos plataformas analíticas con medianas separadas >= 1.5x: ahí
la σ* robusta se infla, la ventana de aceptación se ensancha y casi nadie
reprueba, de modo que un "todo aceptable" es un falso negativo.

Uso:
  conda activate concalab
  python scripts/informe_preliminar.py --codigo EA-001-2026
"""

import os
import sys
import json
import html
import argparse
import statistics
from collections import defaultdict, Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calcular_zscore import (  # noqa: E402
    cargar, calcular_agrupado, robust_mean_sd, plataforma, detectar_bimodales,
    N_MINIMO, N_MINIMO_GRUPO, RAZON_BIMODAL, CONFIG_PATH, ANALITOS_POR_GRUPO_PARES,
)


def es_por_pares(a):
    return a.get("evaluacion") == "grupo_pares"


def evaluados(a):
    """Laboratorios con Z-Score calculado (excluye los 'NE' sin grupo de pares)."""
    return [l for l in a["laboratorios"] if l["z_score"] is not None]

SALIDA_DIR = "support"

# Identidad visual del proyecto.
AZUL, DORADO = "#003f87", "#fdb913"
# Paleta de estado para marcas pequeñas: validada (banda de luminosidad, piso de
# croma, separación CVD y contraste >= 3:1 sobre fondo claro). Los tonos vivos
# del sitio (#28a745/#ffc107/#dc3545) solo se usan en rellenos grandes con texto
# blanco, donde el contraste sí alcanza.
C_A, C_C, C_I = "#1e7e34", "#b8860b", "#c62828"
COLOR_CLASE = {"A": C_A, "C": C_C, "I": C_I}
NOMBRE_CLASE = {"A": "Aceptable", "C": "Cuestionable", "I": "Inaceptable"}

Z_CLAMP = 5.0


def tira_zscore(labs, ancho=360, alto=60):
    """
    Tira de dispersión de Z-Score: eje horizontal de −5 a +5, un punto por
    laboratorio. La POSICIÓN es la codificación primaria (severidad); el color
    solo la refuerza, y el detalle va en el tooltip y en las tablas.
    Deja ver de un vistazo si la distribución es unimodal o está partida.
    """
    # El viewBox se dibuja 1:1 con el ancho en CSS: si se escalara, los puntos y
    # las etiquetas de escala quedarían por debajo de su tamaño legible.
    m_izq, m_der, m_sup = 20, 20, 6
    util = ancho - m_izq - m_der
    cy = m_sup + 17

    def x(z):
        return m_izq + (max(-Z_CLAMP, min(Z_CLAMP, z)) + Z_CLAMP) / (2 * Z_CLAMP) * util

    p = [f'<svg class="tira" viewBox="0 0 {ancho} {alto}" role="img" '
         f'aria-label="Dispersión de Z-Score por laboratorio">']
    # Zona aceptable |z| <= 2, banda de referencia recesiva.
    p.append(f'<rect x="{x(-2):.1f}" y="{m_sup}" width="{x(2)-x(-2):.1f}" height="34" '
             f'fill="{C_A}" opacity="0.08" rx="3"/>')
    for z, tono in ((-3, C_I), (-2, C_C), (2, C_C), (3, C_I)):
        p.append(f'<line x1="{x(z):.1f}" y1="{m_sup}" x2="{x(z):.1f}" y2="{m_sup+34}" '
                 f'stroke="{tono}" stroke-width="1" stroke-dasharray="3 3" opacity="0.55"/>')
    p.append(f'<line x1="{x(0):.1f}" y1="{m_sup}" x2="{x(0):.1f}" y2="{m_sup+34}" '
             f'stroke="#9aa3b2" stroke-width="1"/>')

    # Puntos: jitter vertical determinista para separar solapamientos, con anillo
    # del color de superficie para que los cúmulos sigan siendo contables.
    for i, l in enumerate(sorted(labs, key=lambda l: l["z_score"])):
        z = l["z_score"]
        dy = ((i % 5) - 2) * 3.6
        fuera = "  (fuera de escala)" if abs(z) > Z_CLAMP else ""
        p.append(
            f'<circle cx="{x(z):.1f}" cy="{cy+dy:.1f}" r="4.2" fill="{COLOR_CLASE[l["clasificacion"]]}" '
            f'stroke="#ffffff" stroke-width="1.6" opacity="0.92">'
            f'<title>{html.escape(l["id"])} — z = {z:+.2f} ({NOMBRE_CLASE[l["clasificacion"]]}){fuera}\n'
            f'Resultado: {l["resultado"]:g}\n{html.escape(l["instrumento"] or "equipo no declarado")}</title>'
            f"</circle>"
        )

    for z, etq in ((-Z_CLAMP, "−5"), (0, "0"), (Z_CLAMP, "+5")):
        p.append(f'<text x="{x(z):.1f}" y="{alto-3}" text-anchor="middle" '
                 f'class="tira-etq">{etq}</text>')
    p.append("</svg>")
    return "".join(p)


def construir_html(codigo, analitos, por_analito, bimodales):
    tot = Counter()
    for a in analitos:
        tot.update(l["clasificacion"] for l in a["laboratorios"])
    n_eval = sum(tot.values())
    n_labs = len({l["id"] for a in analitos for l in a["laboratorios"]})

    def pct(k):
        return tot[k] / n_eval * 100 if n_eval else 0

    # Salud por analito: peor primero, que es donde hay que mirar.
    def frac_ok(a):
        ev = evaluados(a)
        return sum(1 for l in ev if l["clasificacion"] == "A") / len(ev) if ev else 1.0

    orden = sorted(analitos, key=lambda a: (frac_ok(a), -(a.get("cv") or a.get("cv_global", 0))))

    # ── Tabla de salud ────────────────────────────────────────────────────────
    filas = []
    for a in orden:
        ev = evaluados(a)
        c = Counter(l["clasificacion"] for l in ev)
        n_ev = len(ev)
        p_ok = c["A"] / n_ev * 100 if n_ev else 0
        marca = bimodales.get(a["nombre"])
        aviso = ""
        if es_por_pares(a):
            gs = [g for g in a["grupos"] if g["evaluado"]]
            aviso = (f'<span class="chip chip-pares" title="'
                     + ' | '.join(f'{g["nombre"]}: n={g["n"]}, X*={g["valor_asignado"]:g}, CV={g["cv"]:.1f}%'
                                  for g in gs)
                     + f'">grupo de pares · {len(gs)} grupos</span>')
            sin_ev = sum(g["n"] for g in a["grupos"] if not g["evaluado"])
            if sin_ev:
                aviso += f'<span class="chip chip-n">{sin_ev} sin evaluar</span>'
        elif marca:
            aviso = (f'<span class="chip chip-alerta" title="Dos plataformas con medianas '
                     f'separadas {marca[0]:.1f}x">σ* inflada · {marca[0]:.1f}x</span>')
        elif a["cv"] > 30:
            aviso = '<span class="chip chip-cv">CV muy alto</span>'
        elif a["cv"] > 15:
            aviso = '<span class="chip chip-cv-leve">CV alto</span>'
        if not es_por_pares(a) and not a["n_suficiente"]:
            aviso += f'<span class="chip chip-n">n &lt; {N_MINIMO}</span>'

        d = n_ev or 1
        barra = (f'<div class="barra" title="{p_ok:.0f}% aceptable">'
                 f'<span style="width:{c["A"]/d*100:.1f}%;background:{C_A}"></span>'
                 f'<span style="width:{c["C"]/d*100:.1f}%;background:{C_C}"></span>'
                 f'<span style="width:{c["I"]/d*100:.1f}%;background:{C_I}"></span></div>')

        # Precalculadas: en los analitos por pares no hay X*, σ* ni CV únicos, y
        # anidar estas condicionales dentro del f-string lo vuelve ilegible.
        pares = es_por_pares(a)
        celda_n = f"{n_ev}" if n_ev == a["n"] else f"{n_ev} / {a['n']}"
        celda_x = "—" if pares else format(a["valor_asignado"], "g")
        celda_s = "—" if pares else format(a["sd_robusta"], "g")
        celda_cv = "—" if pares else f"{a['cv']:.1f}%"
        clase_cv = "" if pares else ("cv-mal" if a["cv"] > 30 else ("cv-ojo" if a["cv"] > 15 else ""))

        filas.append(f"""<tr>
  <td class="an"><strong>{html.escape(a['nombre'])}</strong><br><span class="u">{html.escape(a['unidad'])}</span>{aviso}</td>
  <td class="num">{celda_n}</td>
  <td class="num">{celda_x}</td>
  <td class="num">{celda_s}</td>
  <td class="num {clase_cv}">{celda_cv}</td>
  <td class="num">{c['A']}</td><td class="num">{c['C']}</td><td class="num">{c['I']}</td>
  <td class="pct">{barra}<span class="pctn">{p_ok:.0f}%</span></td>
  <td class="tira-td">{tira_zscore(ev)}</td>
</tr>""")

    # ── Atípicos por laboratorio (detecta patrones sistemáticos) ──────────────
    por_lab = defaultdict(list)
    for a in analitos:
        for l in a["laboratorios"]:
            if l["clasificacion"] in ("C", "I"):
                por_lab[l["id"]].append((a, l))
    lab_filas = []
    for cod in sorted(por_lab, key=lambda c: (-len(por_lab[c]), c)):
        casos = sorted(por_lab[cod], key=lambda x: x[1]["z_score"])
        n_i = sum(1 for _, l in casos if l["clasificacion"] == "I")
        zs = [l["z_score"] for _, l in casos]
        # Mayoría, no unanimidad: un laboratorio con sesgo común puede tener aun así
        # algún analito desviado en sentido contrario (electrolitos y proteínas suelen
        # comportarse distinto), y exigir unanimidad dejaría fuera los casos más claros.
        n_bajo = sum(1 for z in zs if z < 0)
        n_alto = len(zs) - n_bajo
        dominante, n_dom = ("por debajo", n_bajo) if n_bajo >= n_alto else ("por encima", n_alto)
        sistem = ""
        if len(casos) >= 5 and n_dom / len(casos) >= 0.7:
            detalle_signo = (f"Todos los {len(casos)} analitos atípicos" if n_dom == len(casos)
                             else f"{n_dom} de los {len(casos)} analitos atípicos")
            sistem = (f'<span class="chip chip-alerta">desvío sistemático · {dominante}</span>'
                      f'<div class="nota-lab">{detalle_signo} se desvían {dominante}. '
                      f'Un sesgo de un mismo sentido en tantos analitos rara vez es analítico: '
                      f'revisar primero qué muestra se procesó.</div>')
        det = " ".join(
            f'<span class="pil" style="border-color:{COLOR_CLASE[l["clasificacion"]]}">'
            f'{html.escape(a["nombre"])} <b>{l["z_score"]:+.1f}</b></span>'
            for a, l in casos)
        lab_filas.append(f"""<tr>
  <td class="lab"><strong>{html.escape(cod)}</strong>{sistem}</td>
  <td class="num">{len(casos)}</td><td class="num">{n_i}</td>
  <td>{det}</td>
</tr>""")

    # ── Atípicos por analito, con equipo y método ─────────────────────────────
    bloques = []
    for a in orden:
        at = [l for l in a["laboratorios"] if l["clasificacion"] in ("C", "I")]
        if not at:
            continue
        filas_at = "".join(
            f'<tr><td><strong>{html.escape(l["id"])}</strong></td>'
            f'<td class="num">{l["resultado"]:g}</td>'
            f'<td class="num" style="color:{COLOR_CLASE[l["clasificacion"]]};font-weight:700">{l["z_score"]:+.2f}</td>'
            f'<td><span class="badge-cl" style="background:{COLOR_CLASE[l["clasificacion"]]}">'
            f'{l["clasificacion"]}</span> {NOMBRE_CLASE[l["clasificacion"]]}</td>'
            f'<td class="txt">{html.escape(l["metodo"] or "—")}</td>'
            f'<td class="txt">{html.escape(l["instrumento"] or "—")}</td></tr>'
            for l in sorted(at, key=lambda l: l["z_score"]))
        bloques.append(f"""<details class="det"><summary>
  <strong>{html.escape(a['nombre'])}</strong>
  <span class="sum-meta">{(' · '.join(f"{g['nombre']}: X* = {g['valor_asignado']:g}, σ* = {g['sd_robusta']:g}" for g in a['grupos'] if g['evaluado'])) if es_por_pares(a) else f"X* = {a['valor_asignado']:g} {html.escape(a['unidad'])} · σ* = {a['sd_robusta']:g}"} · {len(at)} atípico(s)</span></summary>
  <table class="t-at"><thead><tr><th>Lab</th><th>Resultado</th><th>Z</th><th>Clasificación</th>
  <th>Método</th><th>Instrumento</th></tr></thead><tbody>{filas_at}</tbody></table></details>""")

    # ── Aviso de bimodalidad ──────────────────────────────────────────────────
    aviso_bim = ""
    if bimodales:
        items = ""
        for nom, (razon, grupos) in sorted(bimodales.items(), key=lambda x: -x[1][0]):
            a = next(x for x in analitos if x["nombre"] == nom)
            c = Counter(l["clasificacion"] for l in a["laboratorios"])
            gs = " · ".join(f"{html.escape(g)}: n={n}, mediana={m:g}" for g, n, m in grupos)
            items += (f"<li><strong>{html.escape(nom)}</strong> — plataformas separadas "
                      f"<strong>{razon:.1f}x</strong> ({gs}).<br>"
                      f"Agrupado da σ* = {a['sd_robusta']:g} sobre X* = {a['valor_asignado']:g} "
                      f"(CV {a['cv']:.1f}%), y con esa ventana clasifica "
                      f"<strong>{c['A']} aceptables / {c['C']} cuestionables / {c['I']} inaceptables</strong>: "
                      f"casi nadie reprueba porque el criterio se ensanchó, no porque el desempeño sea bueno.</li>")
        aviso_bim = f"""<div class="alerta">
  <h3>Estos analitos NO se pueden leer en la tabla agrupada</h3>
  <p>Conviven dos plataformas analíticas que no son comparables entre sí. El Algoritmo A no
  converge a un centro único, infla la σ* robusta y la ventana de aceptación se abre tanto que
  absorbe casi todo. <strong>Un "todo aceptable" aquí es un falso negativo</strong>, no un buen resultado.</p>
  <ul>{items}</ul>
  <p class="cierre">Requieren evaluación por grupo de pares (ISO 13528 §7) o quedar fuera de la
  evaluación de esta ronda. Mientras tanto, ignorar sus columnas A/C/I.</p></div>"""

    gen = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Preliminar {html.escape(codigo)} — Química Clínica (interno)</title>
<style>
  :root {{ --azul:{AZUL}; --dorado:{DORADO}; --ink:#1f2430; --ink2:#5a6472; --linea:#dfe4ee; --sup:#fcfcfb; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:'IBM Plex Sans','Segoe UI',Arial,sans-serif; color:var(--ink);
         margin:0; padding:2rem 1.5rem 4rem; background:#f4f6fb; line-height:1.55; }}
  .wrap {{ max-width:1500px; margin:0 auto; }}
  .aviso {{ background:#fff8e1; border-left:4px solid var(--dorado); padding:.7rem 1.1rem;
            font-size:.85rem; border-radius:4px; margin-bottom:1.4rem; }}
  h1 {{ color:var(--azul); font-size:1.6rem; margin:0 0 .2rem; letter-spacing:-.01em; }}
  .sub {{ color:var(--ink2); font-size:.95rem; margin-bottom:1.6rem; }}
  h2 {{ color:var(--azul); font-size:1.12rem; margin:2.4rem 0 .3rem;
        border-bottom:2px solid var(--dorado); padding-bottom:.35rem; display:inline-block; }}
  .h2n {{ color:var(--ink2); font-size:.85rem; margin:.35rem 0 1rem; max-width:70ch; }}
  .tarjetas {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:.8rem; margin-bottom:1.6rem; }}
  .tj {{ padding:.9rem 1rem; border-radius:10px; color:#fff; }}
  .tj .n {{ font-size:1.7rem; font-weight:700; line-height:1.1; }}
  .tj .l {{ font-size:.78rem; opacity:.93; }}
  .panel {{ background:#fff; border:1px solid var(--linea); border-radius:10px; overflow-x:auto; }}
  table {{ border-collapse:collapse; width:100%; font-size:.84rem; }}
  th {{ background:var(--azul); color:#fff; padding:.55rem .6rem; text-align:left;
        font-weight:600; font-size:.76rem; text-transform:uppercase; letter-spacing:.03em; white-space:nowrap; }}
  td {{ padding:.5rem .6rem; border-bottom:1px solid var(--linea); vertical-align:middle; }}
  tr:last-child td {{ border-bottom:none; }}
  tbody tr:hover {{ background:#f7f9fd; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .an {{ min-width:210px; }} .u {{ color:var(--ink2); font-size:.76rem; }}
  .txt {{ font-size:.78rem; color:var(--ink2); max-width:190px; }}
  .cv-mal {{ color:{C_I}; font-weight:700; }} .cv-ojo {{ color:{C_C}; font-weight:700; }}
  .chip {{ display:inline-block; font-size:.68rem; padding:.1rem .42rem; border-radius:3px;
           margin-left:.3rem; font-weight:600; white-space:nowrap; }}
  .chip-alerta {{ background:#fdecea; color:{C_I}; border:1px solid {C_I}55; }}
  .chip-cv {{ background:#fdecea; color:{C_I}; }} .chip-cv-leve {{ background:#fdf5e3; color:{C_C}; }}
  .chip-n {{ background:#eef1f7; color:var(--ink2); }}
  .chip-pares {{ background:#eef3fb; color:{AZUL}; border:1px solid {AZUL}44; }}
  .barra {{ display:flex; height:7px; border-radius:4px; overflow:hidden; background:#eef1f7; min-width:82px; }}
  .barra span {{ display:block; }} .barra span + span {{ border-left:2px solid var(--sup); }}
  .pct {{ min-width:120px; }} .pctn {{ font-size:.74rem; color:var(--ink2); font-variant-numeric:tabular-nums; }}
  .tira {{ width:360px; height:auto; display:block; }} .tira-td {{ width:372px; }}
  .tira-etq {{ font-size:9px; fill:#9aa3b2; }}
  .pil {{ display:inline-block; font-size:.72rem; padding:.1rem .45rem; margin:.11rem .16rem .11rem 0;
          border:1px solid; border-radius:11px; background:#fff; white-space:nowrap; }}
  .lab {{ min-width:180px; }}
  .nota-lab {{ font-size:.75rem; color:var(--ink2); margin-top:.3rem; max-width:34ch; }}
  .badge-cl {{ display:inline-block; color:#fff; font-weight:700; font-size:.7rem;
               width:1.15rem; text-align:center; border-radius:3px; }}
  .alerta {{ background:#fff; border:1px solid {C_I}44; border-left:4px solid {C_I};
             border-radius:8px; padding:1rem 1.3rem; margin-bottom:1.6rem; }}
  .alerta h3 {{ color:{C_I}; margin:0 0 .4rem; font-size:1rem; }}
  .alerta p {{ font-size:.86rem; margin:.45rem 0; }}
  .alerta ul {{ font-size:.85rem; margin:.6rem 0; padding-left:1.1rem; }}
  .alerta li {{ margin-bottom:.55rem; }}
  .cierre {{ border-top:1px solid var(--linea); padding-top:.55rem; font-weight:600; }}
  .det {{ background:#fff; border:1px solid var(--linea); border-radius:8px; margin-bottom:.5rem; }}
  summary {{ padding:.6rem .9rem; cursor:pointer; font-size:.9rem; }}
  summary:hover {{ background:#f7f9fd; }}
  .sum-meta {{ color:var(--ink2); font-size:.78rem; margin-left:.5rem; }}
  .t-at {{ border-top:1px solid var(--linea); }}
  .t-at th {{ background:#eef1f7; color:var(--azul); }}
  .leyenda {{ display:flex; gap:1.1rem; flex-wrap:wrap; font-size:.8rem; color:var(--ink2);
              margin:.7rem 0 0; align-items:center; }}
  .leyenda i {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:.32rem; }}
  footer {{ margin-top:2.5rem; color:var(--ink2); font-size:.78rem; border-top:1px solid var(--linea); padding-top:.8rem; }}
</style></head><body><div class="wrap">

<div class="aviso"><strong>Documento interno de trabajo — no publicar.</strong> Preliminar y sin revisar.
Incluye método e instrumento, que pueden re-identificar laboratorios. No commitear ni enviar a participantes.</div>

<h1>Informe preliminar — {html.escape(codigo)}</h1>
<div class="sub">Química Clínica · Evaluación <strong>agrupada</strong> (todos los laboratorios juntos, sin separar
por instrumento) · ISO 13528 Algoritmos A y S · {n_labs} laboratorios · generado {gen}</div>

<div class="tarjetas">
  <div class="tj" style="background:#28a745"><div class="n">{tot['A']}</div><div class="l">Aceptables · {pct('A'):.1f}%</div></div>
  <div class="tj" style="background:#b8860b"><div class="n">{tot['C']}</div><div class="l">Cuestionables · {pct('C'):.1f}%</div></div>
  <div class="tj" style="background:#c62828"><div class="n">{tot['I']}</div><div class="l">Inaceptables · {pct('I'):.1f}%</div></div>
  <div class="tj" style="background:{AZUL}"><div class="n">{n_eval}</div><div class="l">Evaluaciones</div></div>
  <div class="tj" style="background:#4a5568"><div class="n">{len(analitos)}</div><div class="l">Analitos</div></div>
</div>

{aviso_bim}

<h2>1 · Salud por analito</h2>
<div class="h2n">Ordenado de peor a mejor desempeño. La tira muestra un punto por laboratorio ubicado según
su Z-Score; la posición es lo que indica severidad y el color solo la refuerza. Una nube partida en dos
delata mezcla de plataformas. Pasa el cursor sobre un punto para ver el laboratorio.</div>
<div class="panel"><table>
<thead><tr><th>Analito</th><th class="num">n</th><th class="num">X*</th><th class="num">σ*</th>
<th class="num">CV</th><th class="num">A</th><th class="num">C</th><th class="num">I</th>
<th>% aceptable</th><th>Dispersión de Z-Score (−5 … +5)</th></tr></thead>
<tbody>{''.join(filas)}</tbody></table></div>
<div class="leyenda">
  <span><i style="background:{C_A}"></i>A · Aceptable |z| ≤ 2</span>
  <span><i style="background:{C_C}"></i>C · Cuestionable 2 &lt; |z| &lt; 3</span>
  <span><i style="background:{C_I}"></i>I · Inaceptable |z| ≥ 3</span>
  <span>Puntos fuera de ±5 se dibujan en el borde.</span>
</div>

<h2>2 · Laboratorios con resultados atípicos</h2>
<div class="h2n">Ordenado por cantidad de analitos fuera de |z| ≤ 2. Un laboratorio desviado en muchos
analitos <em>en el mismo sentido</em> apunta a una causa común —muestra equivocada, dilución, error de
registro— y no a fallas analíticas independientes.</div>
<div class="panel"><table>
<thead><tr><th>Lab</th><th class="num">Atípicos</th><th class="num">Inaceptables</th>
<th>Analitos afectados (Z-Score)</th></tr></thead>
<tbody>{''.join(lab_filas) if lab_filas else '<tr><td colspan="4">Sin atípicos.</td></tr>'}</tbody></table></div>

<h2>3 · Detalle de cada caso atípico</h2>
<div class="h2n">Con el método y el equipo declarados, para distinguir error analítico de efecto de
plataforma o error de transcripción. Clic para desplegar.</div>
{''.join(bloques) if bloques else '<p>Sin casos atípicos.</p>'}

<footer>CONCALAB-UASD · Preliminar {html.escape(codigo)} · Evaluación agrupada, sin grupos de pares.
Los analitos marcados con <span class="chip chip-alerta">σ* inflada</span> no son interpretables en esta modalidad.</footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Informe preliminar de triaje (interno).")
    ap.add_argument("--codigo", help="Código de ensayo (por defecto: ronda activa)")
    args = ap.parse_args()

    codigo = args.codigo
    if not codigo:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            codigo = json.load(f)["ronda_activa"]["codigo"]

    por_analito, _ = cargar(codigo)
    if not por_analito:
        sys.exit(f"No hay resultados de Química Clínica para {codigo}.")

    analitos = calcular_agrupado(por_analito, por_grupo_pares=ANALITOS_POR_GRUPO_PARES)
    bimodales = detectar_bimodales(calcular_agrupado(por_analito), por_analito)
    # Los resueltos por grupo de pares ya no son un problema pendiente.
    bimodales = {k: v for k, v in bimodales.items() if k not in ANALITOS_POR_GRUPO_PARES}

    os.makedirs(SALIDA_DIR, exist_ok=True)
    ruta = os.path.join(SALIDA_DIR, f"preliminar_{codigo}-quimica.html")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(construir_html(codigo, analitos, por_analito, bimodales))

    n_at = sum(1 for a in analitos for l in a["laboratorios"] if l["clasificacion"] in ("C", "I"))
    n_ne = sum(1 for a in analitos for l in a["laboratorios"] if l["clasificacion"] == "NE")
    if ANALITOS_POR_GRUPO_PARES:
        print(f"  Por grupo de pares: {', '.join(sorted(ANALITOS_POR_GRUPO_PARES))}"
              + (f"   (sin evaluar: {n_ne})" if n_ne else ""))
    print(f"  Analitos: {len(analitos)}   Casos atípicos: {n_at}")
    if bimodales:
        print(f"  Marcados por bimodalidad: {', '.join(sorted(bimodales))}")
    print(f"  Informe preliminar: {ruta}")


if __name__ == "__main__":
    main()
