"""
Cálculo de Z-Score por analito — ISO/IEC 17043 & ISO 13528 (Algoritmos A y S).

Lee el CSV crudo que produce scripts/extraer_resultados_firebase.py y calcula,
por analito, el valor asignado (X*), la SD robusta (σ*) y el Z-Score de cada
laboratorio, identificado por cod_anonimo.

  z = (x − X*) / σ*     |z| ≤ 2 → A   |   2 < |z| < 3 → C   |   |z| ≥ 3 → I

Modo por defecto: AGRUPADO — un solo valor asignado por analito, con todos los
laboratorios juntos, sin importar el equipo.

Diagnóstico --efecto-metodo: no calcula el informe; compara el resultado agrupado
contra el que se obtendría evaluando cada plataforma analítica por separado
(grupo de pares). Sirve para decidir qué analitos NO deben evaluarse agrupados.

Uso:
  conda activate concalab
  python scripts/calcular_zscore.py --codigo EA-001-2026
  python scripts/calcular_zscore.py --codigo EA-001-2026 --efecto-metodo
"""

import os
import sys
import csv
import json
import argparse
import statistics
from collections import defaultdict, Counter
from datetime import date

import numpy as np

ENTRADA_DIR = "support"
SALIDA_DIR  = os.path.join("data", "informes")
CONFIG_PATH = "data/config.json"

# n mínimo para que la estadística robusta sea defendible (ISO 13528 §7).
N_MINIMO = 12
# Un grupo de pares por debajo de esto no se evalúa por separado.
N_MINIMO_GRUPO = 8
# Separación entre medianas de dos plataformas a partir de la cual el valor
# asignado agrupado deja de ser confiable.
RAZON_BIMODAL = 1.5

def analitos_por_grupo_pares(codigo, area="quimica"):
    """
    Analitos que esta ronda evalúa por GRUPO DE PARES en vez de agrupados
    (ISO 13528 §7). Se leen de data/config.json, no de una constante.

    Vivía como constante de módulo, y eso era una bomba de tiempo: la decisión
    tomada para una ronda se habría aplicado sola a todas las siguientes,
    aunque los datos dijeran otra cosa. Cambiar la base de evaluación de un
    analito es una decisión del proveedor del ensayo y pertenece a la ronda,
    no al código.

    Una ronda sin entrada arranca vacía a propósito: detectar_bimodales()
    avisa qué analitos son candidatos y el proveedor decide y lo declara en
    config.json. No se automatiza cruzando un umbral.
    """
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        print(f"  AVISO: no se pudo leer {CONFIG_PATH} ({e}); se evalúa todo agrupado.")
        return frozenset()

    d = (cfg.get("decisiones_evaluacion") or {}).get(codigo, {}).get(area, {})
    analitos = frozenset(d.get("grupo_pares") or ())

    if not analitos:
        print(f"  AVISO: {codigo}/{area} no declara analitos por grupo de pares en "
              f"{CONFIG_PATH}.\n"
              f"         Se evalúa todo agrupado. Revisa los avisos de bimodalidad:\n"
              f"         un analito bimodal evaluado agrupado produce un falso "
              f"negativo (σ* inflada, nadie reprueba).")
    return analitos


# ====================================================================
# ALGORITMOS ISO 13528
# ====================================================================

def robust_mean_sd(data, max_iterations=50, tol=1e-6):
    """
    Media robusta (X*) y SD robusta (σ*) — Algoritmos A y S de ISO 13528.

    Winsoriza iterativamente a X* ± 1.5σ* hasta converger. Resistente a
    outliers, que es justo lo que abunda en un ensayo de aptitud.
    """
    x = np.sort(np.asarray(data, dtype=float))
    n = len(x)
    if n < 3:
        return float(np.mean(x)), float(np.std(x, ddof=1)) if n > 1 else 0.0

    x_star = float(np.median(x))
    s_star = 1.483 * float(np.median(np.abs(x - x_star)))

    if s_star == 0:
        q75, q25 = np.percentile(x, [75, 25])
        s_star = (q75 - q25) / 1.349
        if s_star == 0:
            s_star = float(np.std(x, ddof=1))

    for _ in range(max_iterations):
        delta = 1.5 * s_star
        x_w = np.clip(x, x_star - delta, x_star + delta)
        x_new = float(np.mean(x_w))
        s_new = 1.134 * float(np.sqrt(np.sum((x_w - x_new) ** 2) / (n - 1)))
        if abs(x_new - x_star) < tol and abs(s_new - s_star) < tol:
            x_star, s_star = x_new, s_new
            break
        x_star, s_star = x_new, s_new

    return x_star, s_star


def clasificar(z):
    if z is None or np.isnan(z):
        return "NR"
    a = abs(z)
    return "A" if a <= 2.0 else ("C" if a < 3.0 else "I")


# ====================================================================
# PLATAFORMA ANALÍTICA
# ====================================================================

def plataforma(instrumento, metodo):
    """
    Clasifica la fila en una plataforma analítica a partir del texto libre.

    El interés real es química seca vs química húmeda: las plataformas secas
    usan sustratos y buffers distintos y en varios analitos leen
    sistemáticamente diferente. Se distinguen entre sí porque no se comportan
    igual.

    Las etiquetas NO nombran al fabricante a propósito. Este valor termina en
    `grupo` dentro del JSON público, junto al cod_anonimo: publicar la marca
    revelaría qué equipo usa cada laboratorio y, en los grupos pequeños (en
    EA-001-2026 la plataforma B tiene n=2), bastaría para re-identificarlo en
    un mercado local reducido. "Seca vs húmeda" es la causa real del efecto de
    método, así que el informe conserva su poder explicativo sin la marca.
    """
    t = f"{instrumento} {metodo}".upper()
    # Cubre las erratas presentes en los datos: FUJIFIMN, DIR-CHEM, FUJI FILM.
    if "FUJI" in t:
        return "Química seca (plataforma A)"
    if "VITRO" in t:
        return "Química seca (plataforma B)"
    return "Química húmeda"


# ====================================================================
# CARGA
# ====================================================================

def a_float(txt):
    try:
        return float(str(txt).strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None


def unidad_canonica(unidades):
    """
    Etiqueta de unidad para mostrar. Solo cosmética: la unidad NO entra en el
    cálculo (ver CLAUDE.md). Se elige la forma más frecuente ignorando
    mayúsculas, descartando vacíos y códigos de instrumento numéricos.
    """
    limpias = [u.strip() for u in unidades if u.strip() and not u.strip().isdigit()]
    if not limpias:
        return "?"
    # Agrupa por forma normalizada y devuelve la grafía más común del grupo.
    grupos = defaultdict(list)
    for u in limpias:
        grupos[u.lower().replace(" ", "")].append(u)
    mayor = max(grupos.values(), key=len)
    return Counter(mayor).most_common(1)[0][0]


def cargar(codigo, categoria="Quím"):
    ruta = os.path.join(ENTRADA_DIR, f"ensayos_{codigo}.csv")
    if not os.path.exists(ruta):
        sys.exit(f"ERROR: no existe {ruta}\n"
                 f"Ejecuta primero: python scripts/extraer_resultados_firebase.py --codigo {codigo}")

    por_analito = defaultdict(list)
    descartados = 0
    ceros = []
    with open(ruta, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["categoria"].startswith(categoria):
                continue
            v = a_float(r["resultado_raw"])
            if v is None:
                descartados += 1
                continue
            # Un 0 en química clínica cuantitativa NO es una medición: ningún
            # analizador devuelve 0.00 de magnesio, HDL, CK o hierro en un suero
            # real. Es el marcador de "no realizado" que escribe el laboratorio
            # cuando la prueba queda fuera de su alcance (en EA-001-2026, LK9 lo
            # acompañó de instrument='-----' y DX6 lo puso solo en 2 de 26).
            # Tratarlo como medición lo penaliza con un z ≈ -3.5 y una no
            # conformidad falsa, y además arrastra el X* y engorda la σ* del
            # analito para todos los demás participantes.
            if v == 0:
                ceros.append((r["cod_anonimo"], r["analito"], r["resultado_raw"]))
                descartados += 1
                continue
            por_analito[r["analito"]].append({
                "cod": r["cod_anonimo"],
                "valor": v,
                "unidad": r["unidad_raw"],
                "metodo": r["metodo"],
                "instrumento": r["instrumento"],
                "plataforma": plataforma(r["instrumento"], r["metodo"]),
            })

    if ceros:
        print(f"\n  AVISO: {len(ceros)} resultado(s) con valor 0 excluidos como "
              f"'no reportado' (ver cargar() para el criterio):")
        for cod, analito, crudo in ceros:
            print(f"    · {cod}  {analito}  (reportado como {crudo!r})")

    return por_analito, descartados


def detectar_bimodales(analitos, por_analito):
    """
    Analitos donde dos plataformas de tamaño suficiente tienen medianas separadas
    >= RAZON_BIMODAL. Ahí el Algoritmo A no converge a un centro único, infla la
    σ* y ensancha tanto la ventana de aceptación que casi nadie reprueba: un
    "todo aceptable" es un falso negativo y NO debe publicarse como desempeño.

    Devuelve {analito: (razon, [(plataforma, n, mediana), …])}.
    """
    marcados = {}
    for a in analitos:
        grupos = defaultdict(list)
        for f in por_analito[a["nombre"]]:
            grupos[f["plataforma"]].append(f["valor"])
        grandes = {g: v for g, v in grupos.items() if len(v) >= N_MINIMO_GRUPO}
        if len(grandes) < 2:
            continue
        med = {g: statistics.median(v) for g, v in grandes.items()}
        alto, bajo = max(med, key=med.get), min(med, key=med.get)
        razon = med[alto] / med[bajo] if med[bajo] else float("inf")
        if razon >= RAZON_BIMODAL:
            marcados[a["nombre"]] = (
                razon,
                sorted(((g, len(grupos[g]), med[g]) for g in grandes), key=lambda x: -x[2]),
            )
    return marcados


# ====================================================================
# CÁLCULO
# ====================================================================

def _stats(valores):
    x, s = robust_mean_sd(valores)
    return round(x, 2), round(s, 2), round((s / x * 100) if x else 0.0, 1)


def calcular_agrupado(por_analito, por_grupo_pares=frozenset()):
    """
    Calcula X*, σ* y Z-Score por analito.

    Por defecto todos los laboratorios se evalúan juntos. Los analitos listados
    en `por_grupo_pares` se evalúan por grupo de pares (ISO 13528 §7): cada
    plataforma analítica obtiene su propio valor asignado, porque sus resultados
    no son comparables entre sí y un único X* no describe a ninguno de los dos
    grupos. Un grupo con menos de N_MINIMO_GRUPO participantes no da estadística
    defendible: esos laboratorios se reportan SIN evaluar (clasificación 'NE'),
    no se anexan al grupo más parecido.
    """
    analitos = []
    for nombre in sorted(por_analito):
        filas = por_analito[nombre]
        unidad = unidad_canonica([f["unidad"] for f in filas])

        def entrada(f, z, extra=None):
            d = {
                "id": f["cod"],
                "resultado": f["valor"],
                "z_score": None if z is None else round(z, 2),
                "clasificacion": "NE" if z is None else clasificar(z),
                "plataforma": f["plataforma"],
                "metodo": f["metodo"],
                "instrumento": f["instrumento"],
            }
            if extra:
                d.update(extra)
            return d

        if nombre in por_grupo_pares:
            grupos_filas = defaultdict(list)
            for f in filas:
                grupos_filas[f["plataforma"]].append(f)

            grupos, labs = [], []
            for g, gf in sorted(grupos_filas.items(), key=lambda kv: -len(kv[1])):
                evaluable = len(gf) >= N_MINIMO_GRUPO
                if evaluable:
                    gx, gs, gcv = _stats([f["valor"] for f in gf])
                    grupos.append({
                        "nombre": g, "n": len(gf), "evaluado": True,
                        "valor_asignado": gx, "sd_robusta": gs, "cv": gcv,
                        "n_suficiente": len(gf) >= N_MINIMO,
                    })
                    for f in gf:
                        z = (f["valor"] - gx) / gs if gs else None
                        labs.append(entrada(f, z, {"grupo": g}))
                else:
                    grupos.append({
                        "nombre": g, "n": len(gf), "evaluado": False,
                        "motivo": f"Grupo de pares insuficiente (n < {N_MINIMO_GRUPO})",
                    })
                    for f in gf:
                        labs.append(entrada(f, None, {"grupo": g}))

            labs.sort(key=lambda l: (l["z_score"] is None, l["z_score"] or 0))

            # Conteos dentro de cada grupo: el informe los muestra en la tabla
            # resumen. Se calculan aquí para que el navegador no los rehaga.
            for g in grupos:
                c = Counter(l["clasificacion"] for l in labs if l.get("grupo") == g["nombre"])
                g["conteos"] = {"A": c["A"], "C": c["C"], "I": c["I"], "NE": c["NE"]}

            analitos.append({
                "nombre": nombre, "unidad": unidad, "n": len(filas),
                "evaluacion": "grupo_pares",
                "grupos": grupos,
                # Referencia global solo informativa: con dos plataformas separadas
                # no describe a ninguna, así que el informe no la usa para evaluar.
                "cv_global": _stats([f["valor"] for f in filas])[2],
                "laboratorios": labs,
            })
            continue

        x_star, s_star, cv = _stats([f["valor"] for f in filas])
        labs = [entrada(f, (f["valor"] - x_star) / s_star if s_star else None) for f in filas]
        labs.sort(key=lambda l: (l["z_score"] is None, l["z_score"] or 0))

        analitos.append({
            "nombre": nombre, "unidad": unidad, "n": len(filas),
            "evaluacion": "agrupada",
            "valor_asignado": x_star,
            "sd_robusta": s_star,
            "cv": cv,
            "n_suficiente": len(filas) >= N_MINIMO,
            "laboratorios": labs,
        })
    return analitos


def imprimir_agrupado(analitos):
    print("\n" + "=" * 96)
    print("  Z-SCORE POR ANALITO")
    print("=" * 96)
    print(f"  {'Analito':<28}{'n':>4}{'X*':>11}{'σ*':>10}{'CV%':>8}{'A':>5}{'C':>4}{'I':>4}{'NE':>4}  {'Unidad':<9}")
    print("  " + "-" * 92)
    tot = Counter()
    for a in analitos:
        c = Counter(l["clasificacion"] for l in a["laboratorios"])
        tot.update(c)
        unidad = a["unidad"]

        if a.get("evaluacion") == "grupo_pares":
            print(f"  {a['nombre']:<28}{a['n']:>4}{'—':>11}{'—':>10}{'—':>8}"
                  f"{c['A']:>5}{c['C']:>4}{c['I']:>4}{c['NE']:>4}  {unidad:<9}  <<< GRUPO DE PARES")
            for g in a["grupos"]:
                if g["evaluado"]:
                    marca = "" if g.get("n_suficiente", True) else f"  (n < {N_MINIMO})"
                    print(f"      · {g['nombre']:<24}{g['n']:>4}{g['valor_asignado']:>11g}"
                          f"{g['sd_robusta']:>10g}{g['cv']:>8.1f}{marca}")
                else:
                    print(f"      · {g['nombre']:<24}{g['n']:>4}{'sin evaluar':>29}  {g['motivo']}")
            continue

        alerta = "  <<< CV alto" if a["cv"] > 15 else ""
        aviso_n = " (n bajo)" if not a["n_suficiente"] else ""
        print(f"  {a['nombre']:<28}{a['n']:>4}{a['valor_asignado']:>11g}{a['sd_robusta']:>10g}"
              f"{a['cv']:>8.1f}{c['A']:>5}{c['C']:>4}{c['I']:>4}{c['NE']:>4}  {unidad:<9}{alerta}{aviso_n}")

    evaluadas = tot["A"] + tot["C"] + tot["I"]
    print("  " + "-" * 92)
    print(f"  Evaluaciones: {evaluadas}   "
          f"A: {tot['A']} ({tot['A']/evaluadas*100:.1f}%)   "
          f"C: {tot['C']} ({tot['C']/evaluadas*100:.1f}%)   "
          f"I: {tot['I']} ({tot['I']/evaluadas*100:.1f}%)")
    if tot["NE"]:
        print(f"  Sin evaluar (grupo de pares insuficiente): {tot['NE']}")
    print("=" * 96)


# ====================================================================
# DIAGNÓSTICO DE EFECTO DE MÉTODO
# ====================================================================

def efecto_metodo(analitos, por_analito):
    """
    Compara evaluación agrupada vs por grupo de pares (plataforma).

    Para cada analito con al menos dos plataformas de tamaño suficiente:
      - razón entre las medianas de las plataformas (magnitud del sesgo)
      - cuántos laboratorios cambian de clasificación al evaluarse por grupo
    """
    print("\n" + "=" * 92)
    print("  EFECTO DE PLATAFORMA ANALÍTICA — agrupado vs. grupo de pares")
    print("=" * 92)

    afectados = []
    for a in analitos:
        filas = por_analito[a["nombre"]]
        grupos = defaultdict(list)
        for f in filas:
            grupos[f["plataforma"]].append(f)

        grandes = {g: v for g, v in grupos.items() if len(v) >= N_MINIMO_GRUPO}
        if len(grandes) < 2:
            continue

        medianas = {g: statistics.median([f["valor"] for f in v]) for g, v in grandes.items()}
        alto = max(medianas, key=medianas.get)
        bajo = min(medianas, key=medianas.get)
        razon = medianas[alto] / medianas[bajo] if medianas[bajo] else float("inf")

        # Reclasificación dentro del grupo de pares
        cambios, detalle_grupos = 0, []
        for g, v in grandes.items():
            vals = [f["valor"] for f in v]
            gx, gs = robust_mean_sd(vals)
            c_pool = Counter()
            c_peer = Counter()
            for f in v:
                z_pool = (f["valor"] - a["valor_asignado"]) / a["sd_robusta"] if a["sd_robusta"] else float("nan")
                z_peer = (f["valor"] - gx) / gs if gs else float("nan")
                cl_pool, cl_peer = clasificar(z_pool), clasificar(z_peer)
                c_pool[cl_pool] += 1
                c_peer[cl_peer] += 1
                if cl_pool != cl_peer:
                    cambios += 1
            detalle_grupos.append((g, len(v), medianas[g], gx, gs, c_pool, c_peer))

        if razon >= 1.5 or cambios:
            afectados.append((a, razon, cambios, detalle_grupos))

    if not afectados:
        print("  Ningún analito muestra efecto de plataforma relevante.")
        return

    afectados.sort(key=lambda x: -x[1])
    for a, razon, cambios, detalle in afectados:
        print(f"\n  {a['nombre']}  —  razón entre plataformas: {razon:.2f}x"
              f"   |   reclasificarían: {cambios} lab(s)")
        print(f"      X* agrupado = {a['valor_asignado']:g} {a['unidad']}   σ* = {a['sd_robusta']:g}   CV = {a['cv']:.1f}%")
        print(f"      {'Plataforma':<26}{'n':>3}{'mediana':>10}{'X* grupo':>11}{'σ* grupo':>10}"
              f"{'  agrupado A/C/I':>18}{'  por pares A/C/I':>19}")
        for g, n, med, gx, gs, c_pool, c_peer in sorted(detalle, key=lambda d: -d[2]):
            print(f"      {g:<26}{n:>3}{med:>10g}{gx:>11.1f}{gs:>10.1f}"
                  f"{f'{c_pool[chr(65)]}/{c_pool[chr(67)]}/{c_pool[chr(73)]}':>18}"
                  f"{f'{c_peer[chr(65)]}/{c_peer[chr(67)]}/{c_peer[chr(73)]}':>19}")
    print("\n" + "=" * 92)
    print("  Razón >= 1.5x indica que las plataformas no son comparables entre sí y que un")
    print("  único valor asignado penaliza a ambos grupos a la vez (ISO 13528 §7: grupo de pares).")
    print("=" * 92)


# ====================================================================

# Campos que solo existen para el análisis interno. NUNCA deben salir en el JSON
# de data/informes/, que se despliega a GitHub Pages: método e instrumento en
# texto libre permiten re-identificar al laboratorio detrás del cod_anonimo.
CAMPOS_INTERNOS = ("plataforma", "metodo", "instrumento")


# Corte por defecto si config.json no declara estratos. Se replica el criterio
# documentado en vez de fallar: un informe sin estratos es peor que uno con los
# cortes habituales, y validar_informe.py avisa igual si algo no cuadra.
ESTRATOS_POR_DEFECTO = [
    {"clave": "satisfactorio", "nombre": "Satisfactorio",     "descripcion": "ningún no conforme",   "desde": 0, "hasta": 0,    "color": "#1e7e34"},
    {"clave": "atencion",      "nombre": "Requiere atención", "descripcion": "1 a 2 no conformes",   "desde": 1, "hasta": 2,    "color": "#b8860b"},
    {"clave": "correctiva",    "nombre": "Acción correctiva", "descripcion": "3 o más no conformes", "desde": 3, "hasta": None, "color": "#c62828"},
]

# Cuántos laboratorios entran en la nota de concentración de no conformidades.
TOP_CONCENTRACION = 6


def leer_estratos():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f).get("estratos_desempeno") or ESTRATOS_POR_DEFECTO
    except (OSError, ValueError):
        return ESTRATOS_POR_DEFECTO


def consolidar_por_laboratorio(analitos):
    """
    Conteos A/C/I por laboratorio sobre los analitos con evaluación concluyente.

    Excluye los no concluyentes a propósito: con una σ* inflada casi todo sale
    aceptable, así que incluirlos regalaría puntos de conformidad a todos por
    igual. 'NE' no es un resultado evaluado y no suma ni al numerador ni al
    denominador.
    """
    por_lab = {}
    for a in analitos:
        if a.get("evaluacion_confiable") is False:
            continue
        for l in a["laboratorios"]:
            r = por_lab.setdefault(l["id"], {"id": l["id"], "A": 0, "C": 0, "I": 0})
            if l["clasificacion"] in ("A", "C", "I"):
                r[l["clasificacion"]] += 1
    for r in por_lab.values():
        r["n"] = r["A"] + r["C"] + r["I"]
        r["pct_conformidad"] = round(r["A"] / r["n"] * 100, 1) if r["n"] else 0.0
    return sorted(por_lab.values(), key=lambda r: r["id"])


def desempeno_global(analitos):
    """
    Métrica de LABORATORIOS, no de resultados: un laboratorio es satisfactorio
    solo si ninguno de sus analitos salió no conforme.

    Se acompaña siempre de la estratificación y de la concentración de fallas.
    El porcentaje solo no distingue una falla aislada de trece, y si las no
    conformidades están concentradas en pocos laboratorios —como en
    EA-001-2026— la cifra sugiere un problema generalizado y llevaría a la
    acción correctiva equivocada.
    """
    labs = consolidar_por_laboratorio(analitos)
    total = len(labs)
    if not total:
        return None

    conformes = sum(1 for r in labs if r["I"] == 0)

    estratos = []
    for e in leer_estratos():
        hasta = e.get("hasta")
        dentro = [r for r in labs
                  if r["I"] >= e.get("desde", 0) and (hasta is None or r["I"] <= hasta)]
        estratos.append({**e, "laboratorios": len(dentro),
                         "pct": round(len(dentro) / total * 100, 1)})

    con_fallas = sorted((r for r in labs if r["I"] > 0), key=lambda r: -r["I"])
    top = con_fallas[:TOP_CONCENTRACION]
    total_i = sum(r["I"] for r in labs)
    suma_top = sum(r["I"] for r in top)

    return {
        "criterio": "Un laboratorio es satisfactorio solo si ninguno de sus "
                    "analitos resultó no conforme.",
        "laboratorios": total,
        "conformes": conformes,
        "pct_conformes": round(conformes / total * 100, 1),
        "estratos": estratos,
        "concentracion": {
            "laboratorios": len(top),
            "no_conformes": suma_top,
            "no_conformes_total": total_i,
            "pct": round(suma_top / total_i * 100, 1) if total_i else 0.0,
        },
        "por_laboratorio": labs,
        "analitos_excluidos": [a["nombre"] for a in analitos
                               if a.get("evaluacion_confiable") is False],
    }


def escribir_json(codigo, analitos, area="quimica", bimodales=None):
    bimodales = bimodales or {}
    tot = Counter()
    for a in analitos:
        tot.update(l["clasificacion"] for l in a["laboratorios"])

    # Copia saneada: se publica solo lo que el informe necesita dibujar.
    limpios = []
    for a in analitos:
        # Un analito bimodal resuelto por grupo de pares SÍ es confiable: la
        # separación en grupos es justamente lo que corrige la σ* inflada.
        b = None if a.get("evaluacion") == "grupo_pares" else bimodales.get(a["nombre"])
        c = Counter(l["clasificacion"] for l in a["laboratorios"])
        limpios.append({
            **a,
            # Los conteos se calculan aquí y no en el navegador: el JS los
            # recalculaba en dos sitios distintos del mismo archivo, y cada
            # ronda clonaba esa lógica sin forma de auditarla.
            "conteos": {"A": c["A"], "C": c["C"], "I": c["I"], "NE": c["NE"]},
            "evaluacion_confiable": b is None,
            "aviso_bimodal": None if b is None else {
                "razon": round(b[0], 2),
                "grupos": [{"plataforma": g, "n": n, "mediana": round(m, 2)} for g, n, m in b[1]],
            },
            "laboratorios": [
                {k: v for k, v in l.items() if k not in CAMPOS_INTERNOS}
                for l in a["laboratorios"]
            ],
        })
    analitos = limpios
    doc = {
        "codigo": codigo,
        "area": area,
        "fecha": date.today().isoformat(),
        "metodologia": "ISO/IEC 17043 & ISO 13528 (Estadística Robusta)",
        "evaluacion": "agrupada",
        "resumen": {
            "laboratorios": len({l["id"] for a in analitos for l in a["laboratorios"]}),
            "aceptables": tot["A"],
            "cuestionables": tot["C"],
            "inaceptables": tot["I"],
            "sin_evaluar": tot["NE"],
            "total": tot["A"] + tot["C"] + tot["I"],
        },
        "desempeno_global": desempeno_global(analitos),
        "analitos": analitos,
    }
    os.makedirs(SALIDA_DIR, exist_ok=True)
    ruta = os.path.join(SALIDA_DIR, f"{codigo}-{area}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return ruta


def main():
    ap = argparse.ArgumentParser(description="Calcula Z-Scores por analito (ISO 13528).")
    ap.add_argument("--codigo", help="Código de ensayo (por defecto: ronda activa)")
    ap.add_argument("--efecto-metodo", action="store_true",
                    help="Solo diagnóstico: compara agrupado vs grupo de pares. No escribe JSON.")
    args = ap.parse_args()

    codigo = args.codigo
    if not codigo:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            codigo = json.load(f)["ronda_activa"]["codigo"]
    area = "quimica"

    por_analito, descartados = cargar(codigo)
    if not por_analito:
        sys.exit(f"No hay resultados de Química Clínica para {codigo}.")

    n_labs = len({f["cod"] for v in por_analito.values() for f in v})
    print(f"\nRonda {codigo} — Química Clínica")
    print(f"  Analitos: {len(por_analito)}   Laboratorios: {n_labs}")
    if descartados:
        print(f"  Valores no numéricos descartados: {descartados}")

    # Primera pasada agrupada, solo para detectar bimodalidad sobre datos sin separar.
    bimodales = detectar_bimodales(calcular_agrupado(por_analito), por_analito)

    # Red de seguridad: si aparece un analito bimodal que la ronda no declaró,
    # hay que decidirlo, no dejar que pase silenciosamente.
    por_pares = analitos_por_grupo_pares(codigo, area)
    sin_decidir = sorted(set(bimodales) - por_pares)
    if sin_decidir:
        print(f"\n  AVISO: bimodalidad detectada en analitos que {codigo} NO declara "
              f"en decisiones_evaluacion de {CONFIG_PATH}:")
        for nom in sin_decidir:
            print(f"    · {nom} — plataformas separadas {bimodales[nom][0]:.1f}x")
        print("    Se publicarán como 'no concluyentes'. Revisar con --efecto-metodo.")

    analitos = calcular_agrupado(por_analito, por_grupo_pares=por_pares)
    if por_pares:
        print(f"\n  Evaluados por grupo de pares: {', '.join(sorted(por_pares))}")
    imprimir_agrupado(analitos)

    if args.efecto_metodo:
        efecto_metodo(analitos, por_analito)
        print("\n(Diagnóstico: no se escribió JSON.)")
        return

    ruta = escribir_json(codigo, analitos, bimodales=bimodales)
    if sin_decidir:
        print(f"\n  Marcados como NO concluyentes: {', '.join(sin_decidir)}")
    print(f"  JSON escrito en: {ruta}")


if __name__ == "__main__":
    main()
