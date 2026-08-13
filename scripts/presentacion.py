"""
Presentación de resultados de una ronda (reveal.js) — CONCALAB-UASD.

Qué es
------
La sesión de devolución a los laboratorios participantes. No sustituye al
informe: lo resume y lo explica. El informe se consulta; la presentación se
escucha una vez, así que dice menos cosas y las dice más grandes.

De dónde salen las cifras
-------------------------
Del mismo `data/informes/<codigo>-quimica-clia.json` que dibuja la página web
y que compone el PDF. Es el cuarto consumidor de ese archivo y, como los
otros tres, **no calcula nada**: `evaluar_clia.py` calcula, `validar_informe.py`
verifica, y aquí solo se decide qué mostrar y en qué orden. Teclear un
porcentaje a mano en una diapositiva es exactamente el modo en que el informe
entregado y lo que se dice en la reunión empiezan a divergir.

Las gráficas se reusan de `informe_pdf.py` en SVG, por la misma razón: si se
redibujaran con otro código, el gráfico proyectado y el impreso podrían
contar cosas distintas sin que nada lo detecte.

reveal.js está vendorizado en `assets/vendor/reveal/` (v6.0.1, MIT). No se
carga por CDN: la presentación tiene que abrir aunque la sala no tenga red.

Uso:
  conda activate concalab
  python scripts/presentacion.py --codigo EA-001-2026

  # verla:  python3 -m http.server 8765
  #         http://localhost:8765/publicaciones/presentaciones/EA-001-2026-resumen.html
  # notas del expositor: tecla S · vista general: Esc · ampliar: Alt+clic
"""

import sys
import json
import html
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from informe_pdf import (  # noqa: E402
    fig_estratos, fig_heatmap, fig_zscore, fig_histograma,
    es_no_evaluado, leer_equipo, titulo_humano,
    AZUL, ORO, VERDE, AMARILLO, ROJO, GRIS, MESES, AREAS, RAIZ,
)

SALIDA_DIR = RAIZ / "publicaciones" / "presentaciones"

# Analitos que ilustran un punto concreto de la sesión. Se eligen por nombre y
# no por índice: el orden del JSON cambia si se agrega un analito, y una
# diapositiva que ilustra el efecto de método con el analito equivocado es
# peor que una sin gráfica.
EJEMPLO_METODO = "LDH"          # dos plataformas con medianas separadas 1,9x
EJEMPLO_LECTURA = "Calcio"    # dispersion moderada: las etiquetas no se pisan


def e(t):
    """Escapa para HTML. Los textos del JSON llegan con entidades ya puestas
    en algunos campos, así que se escapa solo lo que se compone aquí."""
    return html.escape(str(t), quote=False)


def num(x, dec=1):
    """Coma decimal: la presentación es en español dominicano."""
    return f"{x:.{dec}f}".replace(".", ",")


def fecha_larga(iso):
    """'2026-08-13' → '13 de agosto de 2026'."""
    y, m, day = (int(x) for x in iso.split("-"))
    return f"{day} de {MESES[m - 1]} de {y}"


def buscar(d, nombre):
    for a in d["analitos"]:
        if a["nombre"] == nombre:
            return a
    return None


# ── Figuras propias de la presentación ────────────────────────────────────
#
# Las tres de aquí no existen en el informe porque responden a preguntas de
# sesión ("¿en qué analitos falló la red?"), no de documento.

def _estilo_slide():
    """Las figuras del informe se leen a 20 cm de los ojos; estas, en una
    pantalla compartida por videollamada, comprimida. Todo sube de tamaño."""
    plt.rcParams.update({
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "figure.dpi": 110,
        "svg.fonttype": "none",   # texto seleccionable y nítido al ampliar
    })


def fig_brecha(d, destino):
    """La distancia entre «% de resultados satisfactorios» y «% de laboratorios
    sin ninguna no conformidad». Es el titular de la ronda y la diapositiva
    que más se va a citar: merece una gráfica propia y no una viñeta."""
    r, g = d["resumen"], d["desempeno_global"]
    pct_res = r["aceptables"] / r["total"] * 100
    pct_lab = g["pct_conformes"]

    fig, ax = plt.subplots(figsize=(8.6, 3.4))
    ys = [1, 0]
    vals = [pct_res, pct_lab]
    ax.barh(ys, vals, color=[AZUL, ROJO], height=0.5)
    for y, v in zip(ys, vals):
        ax.annotate(f"  {num(v)} %", xy=(v, y), va="center",
                    fontsize=17, fontweight="bold", color="#222")
    ax.set_yticks(ys)
    ax.set_yticklabels([
        "Resultados individuales\nsatisfactorios",
        "Laboratorios SIN ninguna\nno conformidad",
    ])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Porcentaje")
    ax.grid(axis="x", linewidth=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(destino, format="svg", bbox_inches="tight")
    plt.close(fig)


def fig_analitos(d, destino):
    """% dentro del criterio por analito, de peor a mejor. Es el consolidado
    por analito del informe hecho gráfica: en una tabla de 26 filas proyectada
    nadie encuentra el fondo de la lista, que es justo el dato accionable."""
    ev = [a for a in d["analitos"] if a["conteos"]["pct_dentro"] is not None]
    ev.sort(key=lambda a: a["conteos"]["pct_dentro"])
    nombres = [a["nombre"] for a in ev]
    vals = [a["conteos"]["pct_dentro"] for a in ev]

    # El color sigue el mismo semáforo del informe, pero aplicado al analito:
    # no es una clasificación oficial —CLIA califica resultados, no analitos—
    # así que la diapositiva lo dice y aquí solo ordena la lectura.
    cols = [ROJO if v < 60 else (AMARILLO if v < 75 else VERDE) for v in vals]

    fig, ax = plt.subplots(figsize=(9.2, 6.4))
    ys = np.arange(len(ev))
    ax.barh(ys, vals, color=cols, height=0.72)
    for y, v in zip(ys, vals):
        ax.annotate(f" {num(v)}%", xy=(v, y), va="center", fontsize=10,
                    color="#333")
    ax.set_yticks(ys)
    ax.set_yticklabels(nombres, fontsize=10.5)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% de resultados dentro del criterio de aceptación (|z| < 3)")
    ax.grid(axis="x", linewidth=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(destino, format="svg", bbox_inches="tight")
    plt.close(fig)


def fig_criterio(destino):
    """La regla de decisión dibujada: dónde caen A, C e I sobre el eje z, y
    que |z| = 3 ES el límite de CLIA. Explicado solo con palabras, «σpt =
    ETa/3» se pierde; con la banda a la vista se entiende de una."""
    fig, ax = plt.subplots(figsize=(9.4, 2.6))
    tramos = [(-6, -3, ROJO), (-3, -2, AMARILLO), (-2, 2, VERDE),
              (2, 3, AMARILLO), (3, 6, ROJO)]
    for x0, x1, c in tramos:
        ax.axvspan(x0, x1, color=c, alpha=0.75)
    for x, txt in [(-3, "−ETa"), (3, "+ETa")]:
        ax.axvline(x, color="#222", lw=1.6, ls="--")
        ax.annotate(txt, xy=(x, 1.06), ha="center", fontsize=12,
                    fontweight="bold", color="#222", annotation_clip=False)
    ax.axvline(0, color="#222", lw=1.2)
    ax.annotate("X*", xy=(0, 1.06), ha="center", fontsize=12,
                fontweight="bold", color="#222", annotation_clip=False)
    for x, txt in [(0, "Satisfactorio\n|z| ≤ 2"), (2.5, "Alerta"),
                   (-2.5, "Alerta"), (4.5, "No satisfactorio"),
                   (-4.5, "No satisfactorio")]:
        ax.annotate(txt, xy=(x, 0.5), ha="center", va="center", fontsize=11,
                    fontweight="bold", color="#fff" if abs(x) > 3 else "#1c2430")
    ax.set_xlim(-6, 6)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xticks([-6, -4, -3, -2, 0, 2, 3, 4, 6])
    ax.set_xlabel("Z-Score")
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    fig.tight_layout()
    fig.savefig(destino, format="svg", bbox_inches="tight")
    plt.close(fig)


# ── Diapositivas ──────────────────────────────────────────────────────────

def pie(codigo, area):
    return (f'<div class="pie-marca"><span>CONCALAB-UASD · {e(area)}</span>'
            f'<span>{e(codigo)}</span></div>')


def slide(contenido, notas="", clase=""):
    c = f' class="{clase}"' if clase else ""
    n = f'\n<aside class="notes">{notas}</aside>' if notas else ""
    return f"<section{c}>\n{contenido}{n}\n</section>"


def divisor(n, titulo):
    return slide(
        f'<div class="portada-inner"><div class="num">{n}</div>'
        f"<h2>{e(titulo)}</h2></div>", clase="divisor")


def portada(d, meta, equipo):
    nombres = "<br>".join(
        f"{titulo_humano(n)} — {titulo_humano(c)}" for n, c in equipo)
    return slide(f"""<div class="portada-inner">
<div class="logos">
  <img src="../../pic/Uasd.png" alt="UASD">
  <img src="../../pic/logo-badge.png" alt="CONCALAB">
</div>
<span class="eyebrow">Programa de Evaluación Externa de la Calidad</span>
<h1>Resultados de la ronda {e(d['codigo'])}</h1>
<p class="subtitulo">{e(meta['area_nombre'])}</p>
<p class="meta">Sesión de devolución a los laboratorios participantes<br>
{e(meta['fecha_sesion'])}<br><br>{nombres}</p>
</div>""", clase="portada", notas="""
Bienvenida. Recordar tres cosas antes de empezar:<br>
1) Esta sesión explica el informe, no lo reemplaza.<br>
2) Nadie en esta sala —ni CONCALAB durante la evaluación— sabe qué
laboratorio es cada identificador L-NNN.<br>
3) Habrá espacio para preguntas al final.""")


def s_introduccion(d):
    return slide(f"""<span class="eyebrow">1 · Introducción</span>
<h2>Qué es CONCALAB-UASD</h2>
<p>Programa de <strong>Control de Calidad de Laboratorios</strong> de la
Universidad Autónoma de Santo Domingo. Organiza ensayos de aptitud
(evaluación externa de la calidad) para laboratorios clínicos del país.</p>
<div class="cols">
<div class="fragment">
<h3>En qué se apoya</h3>
<ul>
<li><strong>ISO/IEC 17043</strong> — requisitos para proveedores de ensayos de aptitud</li>
<li><strong>ISO 13528:2022</strong> — métodos estadísticos</li>
<li><strong>CLIA 42 CFR §493.931</strong> — criterio de aceptación por analito</li>
</ul>
</div>
<div class="fragment">
<h3>Confiabilidad</h3>
<ul>
<li>Evaluación <strong>anónima</strong>: en el informe cada laboratorio es un
identificador público; el nombre no aparece en ningún archivo publicado</li>
<li>Todo el cálculo es <strong>reproducible</strong> y queda versionado</li>
<li>El informe <strong>declara sus propias limitaciones</strong></li>
</ul>
</div>
</div>""", notas="""
Insistir en el anonimato: es la condición para que un lab reporte lo que
realmente midió y no lo que cree que debe salir. Un programa donde conviene
maquillar el resultado no mide nada.""")


def s_objetivos():
    return slide("""<span class="eyebrow">2 · Objetivos del programa</span>
<h2>Para qué sirve participar</h2>
<ul>
<li class="fragment"><strong>Verificar el desempeño analítico</strong> frente a un valor de
referencia externo e independiente del laboratorio.</li>
<li class="fragment"><strong>Detectar sesgo sistemático</strong> — lo que el control interno no
ve: un equipo mal calibrado es <em>consistente</em> consigo mismo todos los días.</li>
<li class="fragment"><strong>Comparar con pares</strong> que usan la misma plataforma analítica.</li>
<li class="fragment"><strong>Generar evidencia objetiva</strong> de evaluación externa para
habilitación y acreditación.</li>
<li class="fragment"><strong>Orientar la mejora</strong>: señalar dónde actuar, con datos.</li>
</ul>
<div class="caja nota fragment">El ensayo de aptitud no es un examen con nota. Es un
instrumento de medición del propio laboratorio.</div>""", notas="""
El segundo punto es el argumento más fuerte y el menos evidente: el control
interno mide repetibilidad contra uno mismo. Si la calibración está corrida,
el control interno sale perfecto todos los días y el sesgo es invisible.
Solo un material externo con valor asignado lo revela.""")


def s_metodologia_1(d):
    c = d["criterios_aceptacion"]
    return slide(f"""<span class="eyebrow">3 · Metodología</span>
<h2>Cómo se obtiene el valor de referencia</h2>
<div class="cols">
<div class="fragment">
<h3>Valor asignado (X*)</h3>
<p>{e(c['valor_asignado'])}</p>
<div class="caja nota"><strong>Algoritmo A</strong> reduce el peso de los
valores extremos en vez de descartarlos. Un consenso calculado con la media
simple se desplaza hacia los errores gruesos.</div>
</div>
<div class="fragment">
<h3>Dispersión (σ*, CV)</h3>
<p>{e(c['dispersion'])}</p>
<div class="caja aviso">Un CV alto <strong>no</strong> reprueba a nadie: dice
que los laboratorios no concuerdan entre sí en ese analito.</div>
</div>
</div>""", notas="""
Punto clave: en esta ronda σ* NO evalúa. Solo informa. Quien haya visto
informes de otros proveedores donde el z se calcula con σ* del grupo, esta
es la diferencia y la próxima diapositiva la explica.""")


def s_metodologia_porque_clia(d):
    return slide(f"""<span class="eyebrow">3 · Metodología</span>
<h2>Por qué CLIA y no el consenso del grupo</h2>
<div class="cols">
<div class="fragment">
<h3>Consenso (σ* del grupo)</h3>
<p>Compara a cada laboratorio con <em>lo que hizo el resto</em>.</p>
<div class="caja clave fragment">Si el grupo está disperso, la ventana de aceptación se
ensancha y <strong>casi nadie reprueba</strong>. Se mide concordancia, no
aptitud clínica.</div>
</div>
<div class="fragment">
<h3>CLIA (ETa fijo)</h3>
<p>Compara a cada laboratorio con <em>el error máximo tolerable para decidir
sobre un paciente</em>.</p>
<div class="caja nota fragment">El criterio <strong>no depende</strong> de cómo le fue
al resto del grupo. Es el mismo cada ronda y entre proveedores.</div>
</div>
</div>
<div class="caja aviso fragment"><strong>Esta ronda se evalúa con CLIA.</strong> Es un
criterio más exigente, y por eso las cifras que veremos son más duras que las
de un informe por consenso. El paciente no se beneficia de que su resultado
sea parecido al de los demás laboratorios: se beneficia de que sea correcto.</div>""",
        notas="""
Esta es LA diapositiva de la sesión. Si alguien pregunta «¿por qué salimos
peor que el año pasado?», la respuesta está aquí: cambió el criterio, no
necesariamente el desempeño. Decirlo antes de mostrar los resultados, no
después, o suena a excusa.""")


def s_metodologia_criterio(d):
    c = d["criterios_aceptacion"]
    niveles = "".join(
        f"<tr><td><strong>{e(n['nombre'])}</strong></td>"
        f"<td>{e(n['regla'])}</td></tr>" for n in c["niveles"])
    return slide(f"""<span class="eyebrow">3 · Metodología</span>
<h2>La regla de decisión</h2>
<p style="font-size:0.8em">Con <strong>σpt = ETa / 3</strong>, un
<strong>|z| = 3</strong> equivale exactamente a desviarse el Error Total
Permitido: es el límite de CLIA §493.931.</p>
<img class="fig ancha" src="__FIGS__/criterio.svg" alt="Escala de Z-Score">
<table class="fragment"><tr><th>Clasificación</th><th>Regla</th></tr>{niveles}</table>""",
        notas="""
Traducirlo a lenguaje de bancada: z = 1 significa que te desviaste un tercio
de lo que CLIA tolera. z = 3, exactamente lo que tolera. z = 6, el doble.""")


def s_metodologia_pares(d):
    pares = [a for a in d["analitos"] if a.get("evaluacion") == "grupo_pares"]
    lista = ", ".join(e(a["nombre"]) for a in pares) or "—"
    ej = buscar(d, EJEMPLO_METODO)
    i = d["analitos"].index(ej) if ej else 0
    return slide(f"""<span class="eyebrow">3 · Metodología</span>
<h2>Evaluación por grupo de pares</h2>
<div class="cols estrecha-izq">
<div>
<p style="font-size:0.78em">Cuando la química seca y la húmeda leen en
escalas distintas, un valor asignado único <strong>penaliza a los dos grupos
a la vez</strong>.</p>
<p style="font-size:0.78em">ISO 13528 §7 admite dar a cada plataforma su
propio X* y su propia evaluación.</p>
<div class="caja nota fragment" style="font-size:0.62em">En esta ronda:
<strong>{lista}</strong>. Un grupo con menos de 8 participantes no se evalúa
(sale como <strong>NE</strong>): compararlo contra un método que no es el
suyo sería incorrecto.</div>
</div>
<div>
<img class="fig alta" src="__FIGS__/metodo.svg" alt="Efecto de método">
<p class="pie">{e(ej['nombre']) if ej else ''} — distribución por plataforma</p>
</div>
</div>""", notas="""
Es química de método, no un desajuste de calibración: son tecnologías que
leen distinto. Por eso no se «corrige»; se evalúa por separado. Y por eso
las etiquetas dicen «química seca / húmeda» y no la marca del equipo:
con grupos pequeños, nombrar la marca permitiría re-identificar labs.""")


def s_alcance(d, meta):
    r = d["resumen"]
    return slide(f"""<span class="eyebrow">3 · Metodología</span>
<h2>Alcance de la ronda</h2>
<div class="cifras">
<div class="cifra"><span class="n">{r['laboratorios']}</span>
<span class="t">laboratorios participantes</span></div>
<div class="cifra"><span class="n">{len(d['analitos'])}</span>
<span class="t">analitos de química clínica</span></div>
<div class="cifra"><span class="n">{r['total'] + r['sin_evaluar']}</span>
<span class="t">resultados recibidos</span></div>
<div class="cifra oro"><span class="n">1</span>
<span class="t">material de ensayo, común a todos</span></div>
</div>
<h3>Cómo se procesó</h3>
<ul style="font-size:0.78em">
<li class="fragment">Reporte por el <strong>portal web</strong> del programa — sin transcripción manual intermedia.</li>
<li class="fragment">Los <strong>ceros</strong> se excluyen del cálculo: ningún analizador devuelve 0,00 en un suero real, así que un 0 es un «no realizado», no una medición.</li>
<li class="fragment"><strong>Auditoría de unidades</strong> sobre todos los resultados no conformes, antes de publicar.</li>
</ul>
<div class="caja nota fragment">Fecha de cálculo de la ronda: {e(meta['fecha_calculo'])}.</div>""",
        notas="""
Lo de los ceros importa y conviene explicarlo: si un 0 entrara al cálculo,
arrastraría el valor asignado y engordaría la σ*, escondiendo desviaciones
reales de OTROS participantes. Perjudica a todos, no solo a quien lo puso.""")


def s_resultados_tarjeta(d):
    r = d["resumen"]
    pct = lambda x: num(x / r["total"] * 100)
    return slide(f"""<span class="eyebrow">4 · Resultados</span>
<h2>Tarjeta general de la ronda</h2>
<div class="cifras">
<div class="cifra fragment"><span class="n sat">{r['aceptables']}</span>
<span class="t">Satisfactorios<br>{pct(r['aceptables'])} %</span></div>
<div class="cifra fragment"><span class="n ale">{r['cuestionables']}</span>
<span class="t">Alerta<br>{pct(r['cuestionables'])} %</span></div>
<div class="cifra alerta fragment"><span class="n">{r['inaceptables']}</span>
<span class="t">No satisfactorios<br>{pct(r['inaceptables'])} %</span></div>
<div class="cifra fragment"><span class="n" style="color:#5a6472">{r['sin_evaluar']}</span>
<span class="t">Sin evaluar (NE)<br>fuera del cálculo</span></div>
</div>
<p class="fragment" style="font-size:0.72em">Los porcentajes se calculan sobre los
<strong>{r['total']}</strong> resultados evaluados. Los
<strong>{r['sin_evaluar']}</strong> sin evaluar quedan fuera del numerador y
del denominador: no son un desempeño, son resultados sobre los que el
programa decidió no pronunciarse.</p>
<div class="caja aviso fragment">Satisfactorio + Alerta = <strong>dentro del criterio
de aceptación</strong>. Una alerta está dentro del Error Total Permitido: es
una advertencia, no un incumplimiento.</div>""", notas="""
Aclarar la suma antes de que lo pregunten: 384+110+324 = 818, y los 40 NE
van aparte. Si se metieran en la misma columna la tabla sumaría 104,9%.""")


def s_resultados_brecha(d):
    g = d["desempeno_global"]
    r = d["resumen"]
    return slide(f"""<span class="eyebrow">4 · Resultados</span>
<h2>La cifra que importa</h2>
<img class="fig ancha" src="__FIGS__/brecha.svg" alt="Resultados vs laboratorios">
<div class="caja clave fragment"><strong>{g['conformes']} de {g['laboratorios']}
laboratorios ({num(g['pct_conformes'])} %)</strong> completaron la ronda sin
ninguna no conformidad. {e(g['criterio'])}</div>
<p class="fragment" style="font-size:0.68em">La distancia entre las dos barras es el punto de
esta sesión: <strong>basta un resultado erróneo para comprometer una decisión
clínica</strong>, sin importar cuántos otros salieron bien.</p>""",
        notas="""
Momento delicado. Decirlo sin rodeos pero con encuadre: es la PRIMERA ronda
evaluada contra CLIA. Es una línea base, no una calificación final. El
objetivo del programa es que esta barra suba en la próxima ronda.""")


def s_resultados_estratos(d):
    g = d["desempeno_global"]
    return slide(f"""<span class="eyebrow">4 · Resultados</span>
<h2>Estratificación del desempeño</h2>
<img class="fig ancha" src="__FIGS__/estratos.svg" alt="Estratos de desempeño">
<p class="fragment" style="font-size:0.7em">El porcentaje global no distingue una falla
aislada de trece. El estrato sí, y de él depende qué acción corresponde.</p>
<div class="caja nota fragment">Los cortes de los estratos son <strong>política del
programa</strong>, declarada y versionada junto al informe — no un umbral
improvisado por ronda.</div>""", notas="""
Aquí conviene ser explícito: la mayoría de la red quedó en «acción
correctiva». No suavizarlo, pero sí acompañarlo del cómo salir: la
diapositiva de recomendaciones da el procedimiento concreto.""")


def s_hallazgo_analitos(d):
    ev = [a for a in d["analitos"] if a["conteos"]["pct_dentro"] is not None]
    peores = sorted(ev, key=lambda a: a["conteos"]["pct_dentro"])[:5]
    lista = ", ".join(e(a["nombre"]) for a in peores)
    return slide(f"""<span class="eyebrow">5 · Hallazgos</span>
<h2>Dónde se concentró la dificultad</h2>
<div class="cols estrecha-izq">
<div>
<p class="fragment" style="font-size:0.74em">Los cinco analitos con menor porcentaje dentro
del criterio fueron:</p>
<div class="caja clave fragment" style="font-size:0.68em">{lista}</div>
<p class="fragment" style="font-size:0.68em">No son analitos exóticos: es
<strong>química básica de alto volumen</strong>, la que más decisiones
clínicas sostiene cada día.</p>
<p class="fragment" style="font-size:0.64em"><em>El color ordena la lectura; CLIA califica
resultados, no analitos.</em></p>
</div>
<div>
<img class="fig alta" src="__FIGS__/analitos.svg" alt="% dentro por analito">
</div>
</div>""", notas="""
Este es el hallazgo más accionable de la ronda para el conjunto: una acción
de mejora sobre estos cinco analitos alcanza a más participantes de golpe
que ir laboratorio por laboratorio.""")


def s_hallazgo_metodo(d):
    pares = [a["nombre"] for a in d["analitos"]
             if a.get("evaluacion") == "grupo_pares"]
    return slide(f"""<span class="eyebrow">5 · Hallazgos</span>
<h2>Efecto de método confirmado</h2>
<ul style="font-size:0.8em">
<li class="fragment">Se confirmó una separación real entre <strong>química seca y húmeda</strong>
en {e(", ".join(pares))}.</li>
<li class="fragment">Evaluarlos agrupados producía un <strong>falso negativo</strong>: una σ*
inflada en la que prácticamente nadie reprobaba.</li>
<li class="fragment">Al separar por grupo de pares, el <strong>CV interno bajó a ~10 %</strong>
y aparecieron las no conformidades reales.</li>
</ul>
<div class="caja aviso fragment"><strong>Un «todo aceptable» puede ser una mala
noticia.</strong> Cuando el grupo está disperso, la ventana de aceptación se
ensancha sola. Por eso el programa vigila la bimodalidad en cada ronda en
lugar de confiar en el porcentaje de aprobados.</div>""", notas="""
Si alguien pregunta por qué su equipo «lee distinto»: no es un defecto del
equipo ni del laboratorio. Son principios de medición diferentes. Lo que sí
debe verificar cada laboratorio es su trazabilidad de calibración.""")


def s_hallazgo_no_evaluado(d, cfg):
    a = next((x for x in d["analitos"] if es_no_evaluado(x)), None)
    if not a:
        return ""
    nota = a.get("nota_sin_evaluar") or ""
    return slide(f"""<span class="eyebrow">5 · Hallazgos</span>
<h2>Un analito se publicó sin calificación</h2>
<h3>{e(a['nombre'])}</h3>
<div class="caja nota fragment" style="font-size:0.68em">{nota}</div>
<ul style="font-size:0.74em">
<li class="fragment">Sale <strong>sin valor asignado</strong> y con todos los resultados en
<strong>NE</strong>: publicar un X* mientras se declara que no hay consenso
defendible sería contradictorio.</li>
<li class="fragment"><strong>No altera el desempeño global</strong> de nadie — solo desaparecen
calificaciones que la estadística de la ronda no podía sostener.</li>
<li class="fragment">La causa está en la <strong>dispersión de los resultados entre
laboratorios</strong>; no se atribuye al material de ensayo.</li>
</ul>
<div class="caja aviso fragment">Preferimos no calificar antes que calificar sobre una
base indefendible. Es una decisión declarada, no un dato faltante.</div>""",
        notas="""
Este punto genera confianza si se explica bien: el programa está dispuesto a
decir «aquí no puedo pronunciarme». Un proveedor que siempre tiene un número
para todo es un proveedor al que hay que revisarle los números.""")


def s_hallazgo_unidades(d):
    return slide("""<span class="eyebrow">5 · Hallazgos</span>
<h2>Ninguna no conformidad se explicó por unidad de reporte</h2>
<p class="fragment" style="font-size:0.8em">Antes de publicar, cada resultado no conforme se
audita contra las conversiones reales de química clínica
(mmol/L ↔ mg/dL, µmol/L ↔ mg/dL, g/L ↔ g/dL, escalas ×10, ×100, ×1000).</p>
<div class="caja nota fragment"><strong>Resultado: 0 casos atribuibles a unidad.</strong>
Las desviaciones observadas son analíticas.</div>
<p class="fragment" style="font-size:0.74em">La comprobación se corre <strong>siempre</strong>:
reportar como no conforme a un laboratorio que en realidad reportó en otra
unidad sería injusto, y el porcentaje global no lo delataría.</p>""",
        notas="""
Sirve para adelantarse a la objeción «seguro fue un problema de unidades».
Se verificó, uno por uno, y no lo fue.""")


def s_mapa(d):
    """El heatmap completo. Va antes de «cómo leer su informe» porque esa
    diapositiva empieza pidiendo que cada uno localice su identificador: sin
    haber visto el mapa, la instrucción no tiene referente."""
    return slide("""<span class="eyebrow">6 · Recomendaciones</span>
<h2>El mapa consolidado</h2>
<img class="fig alta" src="__FIGS__/heatmap.svg" alt="Mapa consolidado">
<p class="pie">Cada fila es un analito; cada columna, un laboratorio.
Verde: satisfactorio · Amarillo: alerta · Rojo: no satisfactorio ·
Gris: sin evaluar</p>""", notas="""
Explicar las tres causas distintas de una celda gris: no reportó ese
analito, su grupo de pares no llegó al mínimo, o el analito no se evaluó.
No son lo mismo y el informe web lo distingue en el tooltip.""")


def s_como_leer(d):
    return slide("""<span class="eyebrow">6 · Recomendaciones</span>
<h2>Cómo leer su propio informe</h2>
<ol style="font-size:0.82em">
<li class="fragment">Localice <strong>su identificador</strong> en el mapa consolidado.</li>
<li class="fragment">Mire el <strong>signo</strong> de sus Z-Score, no solo el valor.</li>
<li class="fragment">Varios z del <strong>mismo signo</strong> → sesgo sistemático:
revise <strong>calibración y trazabilidad</strong>.</li>
<li class="fragment">z <strong>dispersos en ambos signos</strong> → imprecisión:
revise <strong>mantenimiento, reactivos y operador</strong>.</li>
<li class="fragment">Un solo z extremo aislado → revise <strong>transcripción</strong> y el
manejo de la muestra.</li>
</ol>
<div class="caja aviso fragment">Es la diferencia entre recalibrar y cambiar un
procedimiento. <strong>El signo lo dice.</strong> Dos laboratorios con el
mismo porcentaje de conformidad pueden necesitar acciones opuestas.</div>""",
        notas="""
La parte más útil de la sesión para cada participante. Ir despacio: es lo
único que se llevan para actuar el lunes.""")


def s_ejemplo_z(d):
    """El gráfico de Z-Score a ancho completo. Compartía diapositiva con las
    cinco reglas y a media anchura las etiquetas de las barras extremas se
    pisaban unas con otras — ilegible justo en el ejemplo con el que se
    enseña a leer el informe."""
    a = buscar(d, EJEMPLO_LECTURA)
    return slide(f"""<span class="eyebrow">6 · Recomendaciones</span>
<h2>Un ejemplo: {e(a['nombre']) if a else ''}</h2>
<img class="fig ancha alta" src="__FIGS__/lectura.svg" alt="Ejemplo de Z-Score">
<p class="pie">Cada barra es un laboratorio, ordenadas de menor a mayor
Z-Score. Verde: satisfactorio · Amarillo: alerta · Rojo: no satisfactorio.
Las barras que exceden el eje conservan su valor real en la etiqueta.</p>""",
        notas="""
Señalar los dos extremos: a la izquierda quienes leen sistemáticamente
bajo, a la derecha quienes leen alto. Ninguno de los dos lo ve en su control
interno, porque su equipo es consistente consigo mismo.""")


def s_recomendaciones(d):
    g = d["desempeno_global"]
    estr = {x["clave"]: x for x in g["estratos"]}
    cor = estr.get("correctiva", {})
    at = estr.get("atencion", {})
    return slide(f"""<span class="eyebrow">6 · Recomendaciones</span>
<h2>Qué hacer, según su estrato</h2>
<table>
<tr><th>Estrato</th><th class="num">Lab.</th><th>Acción</th></tr>
<tr class="fragment"><td class="nosat">Acción correctiva<br><em>≥3 no conformes</em></td>
<td class="num">{cor.get('laboratorios', 0)}</td>
<td>Abrir <strong>no conformidad formal</strong>, investigar causa raíz por
analito (calibración, control interno, mantenimiento, conservación del
material, transcripción) y documentar la verificación de eficacia.</td></tr>
<tr class="fragment"><td class="ale">Requiere atención<br><em>1–2 no conformes</em></td>
<td class="num">{at.get('laboratorios', 0)}</td>
<td>Revisar los analitos señalados y verificar <strong>calibración y control
interno</strong> de esos ensayos concretos.</td></tr>
<tr class="fragment"><td class="sat">Satisfactorio<br><em>ninguno</em></td>
<td class="num">{estr.get('satisfactorio', {}).get('laboratorios', 0)}</td>
<td>Mantener el desempeño y conservar el informe como
<strong>evidencia objetiva</strong> de evaluación externa.</td></tr>
</table>
<div class="caja nota fragment" style="font-size:0.66em"><strong>Para todos:</strong>
conservar este informe como evidencia de evaluación externa de la calidad
para los procesos de habilitación y acreditación.</div>""", notas="""
Ofrecer acompañamiento: quien no sepa cómo documentar una no conformidad
puede escribir al programa. El objetivo no es señalar, es que la próxima
ronda salga mejor.""")


def s_conclusiones(d):
    g = d["desempeno_global"]
    r = d["resumen"]
    pct_sat = num(r["aceptables"] / r["total"] * 100)
    return slide(f"""<span class="eyebrow">7 · Conclusiones</span>
<h2>Conclusiones de la ronda</h2>
<ol style="font-size:0.72em">
<li class="fragment">Evaluados contra el criterio de <strong>aptitud clínica de CLIA</strong>,
los resultados muestran un <strong>margen amplio de mejora</strong>:
{pct_sat} % de resultados satisfactorios, pero solo
<strong>{g['conformes']} de {g['laboratorios']}</strong> laboratorios sin
ninguna no conformidad.</li>
<li class="fragment">El hallazgo <strong>alcanza a la mayoría de la red</strong>, con un
subconjunto de laboratorios que concentra una parte desproporcionada de las
no conformidades. La mejora requiere acción del conjunto, no solo de unos
pocos.</li>
<li class="fragment">Se confirmó un <strong>efecto de método</strong> entre plataformas; la
evaluación por grupo de pares corrigió un falso negativo.</li>
<li class="fragment">Un analito se publicó <strong>sin calificación</strong> por dispersión
entre laboratorios; no alteró el desempeño global.</li>
<li class="fragment"><strong>Ninguna</strong> no conformidad se explicó por error de unidad.</li>
</ol>
<div class="caja aviso fragment" style="font-size:0.68em">Esta es la
<strong>primera ronda evaluada contra CLIA</strong>. Funciona como línea
base del programa: la referencia para medir la mejora en las próximas.</div>""",
        notas="""
Cerrar con el mensaje de línea base. Y recordar que el informe completo, con
las 26 fichas por analito, está publicado en el sitio.""")


def s_referencias(d):
    c = d["criterios_aceptacion"]
    return slide(f"""<span class="eyebrow">8 · Referencias</span>
<h2>Referencias normativas</h2>
<ul style="font-size:0.7em">
<li><strong>ISO 13528:2022</strong> — <em>Statistical methods for use in
proficiency testing by interlaboratory comparison.</em> Valor asignado por
media robusta (Algoritmo A) y evaluación por grupo de pares (§7).</li>
<li><strong>ISO/IEC 17043</strong> — <em>Conformity assessment. General
requirements for the competence of proficiency testing providers.</em>
Estructura del informe de resultados.</li>
<li><strong>CLIA — 42 CFR §493.931</strong>, regla final CMS-3355-F (2022) y
su corrección de noviembre de 2022. Error Total Permitido por analito.</li>
<li><strong>EFLM Biological Variation Database</strong> — ETa deseable para
los analitos no regulados por CLIA.</li>
</ul>
<div class="caja nota" style="font-size:0.62em">{e(c['eta_fuente'])}</div>""",
        notas="")


def s_anexos(d, meta):
    return slide(f"""<span class="eyebrow">9 · Anexos</span>
<h2>Dónde está todo</h2>
<div class="cols">
<div>
<h3>Informe completo</h3>
<ul style="font-size:0.68em">
<li>Versión web interactiva, con las 26 fichas por analito</li>
<li>Versión PDF firmable, con la estructura ISO/IEC 17043</li>
<li>Anexo con el <strong>ETa aplicado a cada analito</strong> y su fuente</li>
<li>Mapa consolidado de todos los laboratorios</li>
</ul>
</div>
<div>
<h3>Limitaciones declaradas</h3>
<ul style="font-size:0.68em">
<li>El informe declara sus propias brechas frente a la norma</li>
<li>Un informe que calla sus límites se lee con más certeza de la que
soporta</li>
</ul>
</div>
</div>
<div class="caja nota">
<strong>www.concalabuasd.com</strong> → Publicaciones → Informes →
{e(d['codigo'])}</div>""", notas="""
Invitar a las preguntas. Y pedir que cualquier discrepancia con un resultado
propio se comunique al programa: se revisa caso por caso.""")


def s_cierre(d, meta):
    return slide(f"""<div class="portada-inner">
<span class="eyebrow">Gracias</span>
<h1>Preguntas</h1>
<p class="meta">CONCALAB-UASD · Programa de Evaluación Externa de la Calidad<br>
Ronda {e(d['codigo'])} — {e(meta['area_nombre'])}<br><br>
www.concalabuasd.com</p>
</div>""", clase="portada")


# ── Documento ─────────────────────────────────────────────────────────────

PLANTILLA = """<!DOCTYPE html>
<!-- class="print-pdf" NO activa el modo PDF de reveal (eso lo decide la
     query string): desactiva su hoja de impresión de «handout», que al
     imprimir aplanaría la presentación a texto de 20 pt en blanco y negro.
     La paginación la hace css/presentacion.css. -->
<html lang="es" class="print-pdf">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo}</title>
<meta name="description" content="{descripcion}">
<!-- Las fuentes vienen de Google Fonts como en el resto del sitio, con
     respaldo local en la pila de css/presentacion.css: si la sala no tiene
     red, la presentación se ve en Georgia y system-ui, pero se ve. -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../../assets/vendor/reveal/reset.css">
<link rel="stylesheet" href="../../assets/vendor/reveal/reveal.css">
<link rel="stylesheet" href="../../css/presentacion.css">
</head>
<body>
<div class="reveal">
<div class="slides">
{slides}
</div>
</div>
<script src="../../assets/vendor/reveal/reveal.js"></script>
<script src="../../assets/vendor/reveal/plugin/notes.js"></script>
<script src="../../assets/vendor/reveal/plugin/zoom.js"></script>
<script>
    Reveal.initialize({{
        width: 1280,
        height: 720,
        margin: 0.06,
        hash: true,
        slideNumber: 'c/t',
        // Sin transiciones vistosas: la sesión es por videollamada y el
        // vídeo comprimido convierte cualquier animación en un borrón.
        transition: 'fade',
        transitionSpeed: 'fast',
        // El paso a paso queda en la URL: si el navegador se recarga a mitad
        // de la sesión, se vuelve al punto exacto y no al inicio.
        fragmentInURL: true,
        plugins: [RevealNotes, RevealZoom]
    }});
</script>
</body>
</html>
"""


def exportar_pdf(html, destino):
    """Versión estática de la presentación, para repartir tras la sesión.

    Se imprime con Chrome headless —el mismo que ya usa generar_og.py, sin
    dependencias nuevas— y la paginación la hace `@media print` de
    css/presentacion.css: el modo `?print-pdf` de reveal 6.0.1 mete las 30
    diapositivas en una sola hoja.

    Las gráficas siguen siendo vectoriales en el PDF porque son SVG en la
    página: no hay ninguna captura de pantalla por el camino, así que el
    documento aguanta el zoom y la impresión.
    """
    chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser")
                   if shutil.which(c)), None)
    if not chrome:
        print("  AVISO: no se encontró Chrome; el PDF no se generó.")
        return None
    cmd = [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
           "--virtual-time-budget=20000", f"--print-to-pdf={destino}",
           html.as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not destino.exists():
        print(f"  AVISO: Chrome falló al imprimir.\n{r.stderr[-500:]}")
        return None
    return destino


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codigo")
    ap.add_argument("--area", default="quimica")
    ap.add_argument("--solo-figuras", action="store_true")
    ap.add_argument("--fecha", metavar="AAAA-MM-DD",
                    help="fecha de la sesión que va en la portada "
                         "(por defecto: hoy)")
    ap.add_argument("--pdf", action="store_true",
                    help="además del HTML, exporta la versión estática en PDF")
    args = ap.parse_args()

    cfg = json.loads((RAIZ / "data" / "config.json").read_text(encoding="utf-8"))
    codigo = args.codigo or cfg["ronda_activa"]["codigo"]

    ruta_json = RAIZ / "data" / "informes" / f"{codigo}-{args.area}-clia.json"
    if not ruta_json.exists():
        sys.exit(f"No existe {ruta_json}. Corra primero scripts/evaluar_clia.py.")
    d = json.loads(ruta_json.read_text(encoding="utf-8"))
    if d.get("modelo") != "clia":
        sys.exit("El JSON no declara modelo 'clia'.")

    y, m, day = (int(x) for x in d["fecha"].split("-"))
    meta = {
        "area_nombre": AREAS.get(args.area, args.area.title()),
        # Dos fechas distintas, y no da igual cuál va dónde:
        #   · fecha_calculo — cuándo se calculó la ronda. Sale del JSON, está
        #     congelada en config.json y es la que aparece en el informe.
        #   · fecha_sesion  — cuándo se presenta. Por defecto hoy; con
        #     --fecha se fija la del día de la reunión si se prepara antes.
        # Poner la fecha de cálculo en la portada dataría la sesión diez días
        # antes de celebrarse.
        "fecha_calculo": f"{day} de {MESES[m - 1]} de {y}",
        "fecha_sesion": fecha_larga(args.fecha or date.today().isoformat()),
    }

    figs = SALIDA_DIR / f"figs-{codigo}"
    figs.mkdir(parents=True, exist_ok=True)

    print(f"→ Figuras SVG en {figs.relative_to(RAIZ)}…")
    _estilo_slide()
    fig_criterio(figs / "criterio.svg")
    fig_brecha(d, figs / "brecha.svg")
    fig_analitos(d, figs / "analitos.svg")
    fig_estratos(d, figs / "estratos.svg")
    fig_heatmap(d, figs / "heatmap.svg")

    a_metodo = buscar(d, EJEMPLO_METODO)
    if a_metodo:
        fig_histograma(a_metodo, figs / "metodo.svg")
    a_lectura = buscar(d, EJEMPLO_LECTURA)
    if a_lectura:
        fig_zscore(a_lectura, figs / "lectura.svg")
    for f in sorted(figs.glob("*.svg")):
        print(f"   · {f.name}")

    if args.solo_figuras:
        return

    print("→ Diapositivas…")
    equipo = leer_equipo()
    slides = [
        portada(d, meta, equipo),
        divisor(1, "Introducción"),
        s_introduccion(d),
        divisor(2, "Objetivos del programa"),
        s_objetivos(),
        divisor(3, "Metodología de evaluación"),
        s_metodologia_1(d),
        s_metodologia_porque_clia(d),
        s_metodologia_criterio(d),
        s_metodologia_pares(d),
        s_alcance(d, meta),
        divisor(4, "Principales resultados"),
        s_resultados_tarjeta(d),
        s_resultados_brecha(d),
        s_resultados_estratos(d),
        divisor(5, "Principales hallazgos"),
        s_hallazgo_analitos(d),
        s_hallazgo_metodo(d),
        s_hallazgo_no_evaluado(d, cfg),
        s_hallazgo_unidades(d),
        divisor(6, "Recomendaciones"),
        s_mapa(d),
        s_como_leer(d),
        s_ejemplo_z(d),
        s_recomendaciones(d),
        divisor(7, "Conclusiones"),
        s_conclusiones(d),
        s_referencias(d),
        s_anexos(d, meta),
        s_cierre(d, meta),
    ]
    slides = [s for s in slides if s]

    # El pie con la marca va en todas menos portada y divisores (los oculta
    # el CSS); ponerlo aquí evita repetirlo en cada función.
    marca = pie(codigo, meta["area_nombre"])
    slides = [s.replace("\n</section>", f"\n{marca}\n</section>") for s in slides]
    # Las figuras viven en un directorio por ronda, junto al HTML. El
    # marcador se resuelve aquí y no en cada diapositiva para que agregar una
    # ronda no obligue a tocar 28 funciones.
    slides = [s.replace("__FIGS__", f"figs-{codigo}") for s in slides]

    salida = SALIDA_DIR / f"{codigo}-resumen.html"
    salida.write_text(PLANTILLA.format(
        titulo=f"CONCALAB-UASD — Resultados {codigo} · {meta['area_nombre']}",
        descripcion=(f"Sesión de devolución de resultados de la ronda {codigo} "
                     f"de {meta['area_nombre']} a los laboratorios participantes."),
        slides="\n\n".join(slides),
    ), encoding="utf-8")

    print(f"\n  {len(slides)} diapositivas")
    print(f"  {salida.relative_to(RAIZ)}")

    if args.pdf:
        print("\n→ PDF estático…")
        destino = SALIDA_DIR / f"{codigo}-resumen.pdf"
        if exportar_pdf(salida, destino):
            print(f"  {destino.relative_to(RAIZ)}  "
                  f"({destino.stat().st_size / 1e6:.1f} MB)")
    print("\n  Verla:  python3 -m http.server 8765")
    print(f"          http://localhost:8765/{salida.relative_to(RAIZ)}")
    print("  Notas del expositor: tecla S · vista general: Esc\n")


if __name__ == "__main__":
    main()
