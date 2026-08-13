"""
Evaluación por aptitud al uso (modelo CLIA) — EA-XXX-YYYY, Química Clínica.

Pipeline PARALELO al de consenso (calcular_zscore.py). NO lo reemplaza: escribe
un JSON aparte (`<codigo>-quimica-clia.json`) para un informe distinto.

En qué se diferencia del modelo de consenso
--------------------------------------------
- Valor asignado X* = media robusta (Algoritmo A, ISO 13528) — IGUAL que consenso.
- σ* y CV se conservan, pero SOLO informan dispersión; no deciden la evaluación.
- La evaluación NO usa la σ* de los participantes, sino una desviación por
  aptitud al uso: σpt = ETa/3, donde ETa (Error Total Permitido, "δE") sale de
  data/config.json → especificaciones_desempeno. Así:

      z = (Xi − X*) / σpt        con σpt = δE/3   ⇒   |z| = 3  ⟺  desviación = δE

  es decir, |z| ≥ 3 significa estar FUERA del límite de CLIA §493.931. Es el
  mismo criterio que PROASECAL/ESfEQA (el PA de PROASECAL es este z reescalado).

Reusa la maquinaria de calcular_zscore.py (robusto, carga, plataformas, grupos,
consolidación por laboratorio, estratos): aquí solo cambia de dónde sale la σ.

Uso:
  conda activate concalab
  python scripts/evaluar_clia.py --codigo EA-001-2026
"""

import os
import sys
import json
import argparse
import statistics
from collections import defaultdict, Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calcular_zscore import (  # noqa: E402
    cargar, robust_mean_sd, _stats, plataforma, unidad_canonica, clasificar,
    analitos_por_grupo_pares, analitos_sin_evaluar, desempeno_global, CAMPOS_INTERNOS,
    conteos_analito,
    fecha_calculo,
    N_MINIMO, N_MINIMO_GRUPO, SALIDA_DIR, CONFIG_PATH,
)


def leer_especificaciones(area="quimica"):
    """ETa por analito desde config.json. Sin esto no se puede evaluar."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    esp = (cfg.get("especificaciones_desempeno") or {}).get(area)
    if not esp:
        sys.exit(f"ERROR: config.json no declara especificaciones_desempeno.{area}")
    return esp


def delta_e(spec, x_asignado):
    """
    δE (error total permitido, en unidades del analito) resuelto sobre el valor
    asignado. 'pct' = % de X*, 'abs' = valor absoluto; con ambos se toma el mayor
    (regla de CLIA: más permisivo a baja concentración).
    """
    candidatos = []
    if spec.get("pct") is not None:
        candidatos.append(spec["pct"] / 100.0 * abs(x_asignado))
    if spec.get("abs") is not None:
        candidatos.append(float(spec["abs"]))
    return max(candidatos) if candidatos else None


def _spec_publica(spec, dE):
    """Lo que viaja al JSON: la regla declarada + el δE ya resuelto."""
    return {
        "pct": spec.get("pct"),
        "abs": spec.get("abs"),
        "unidad": spec.get("unidad"),
        "regla": spec.get("regla", "unico"),
        "fuente": spec.get("fuente"),
        "delta_e": round(dE, 4) if dE is not None else None,
    }


def _entrada(f, z, extra=None):
    # Se clasifica sobre el z YA redondeado (no el crudo): así lo que se muestra
    # y lo que decide la clasificación son el mismo número. Con el z crudo, un
    # 2.998 se mostraría "3.00" pero clasificaría C — incoherente en el borde.
    zr = None if z is None else round(z, 2)
    d = {
        "id": f["cod"],
        "resultado": f["valor"],
        "z_score": zr,
        "clasificacion": "NE" if zr is None else clasificar(zr),
        "plataforma": f["plataforma"],
        "metodo": f["metodo"],
        "instrumento": f["instrumento"],
    }
    if extra:
        d.update(extra)
    return d


def evaluar(por_analito, especificaciones, por_grupo_pares,
            sin_evaluar=frozenset(), nota_sin_evaluar=None):
    """
    Igual estructura que calcular_agrupado(), pero el z-score usa σpt = δE/3
    en vez de la σ* del consenso. σ* y CV se calculan y se guardan como
    dispersión informativa.
    """
    analitos = []
    for nombre in sorted(por_analito):
        filas = por_analito[nombre]
        unidad = unidad_canonica([f["unidad"] for f in filas])

        # --- Analito SIN CALIFICAR (decisión del proveedor) -----------------
        # Se resuelve antes de buscar el ETa: un analito que no se evalúa no
        # necesita criterio de aceptación, y exigirlo obligaría a declarar un
        # límite que no se va a aplicar.
        if nombre in sin_evaluar:
            valores = [f["valor"] for f in filas]
            labs = [_entrada(f, None) for f in filas]
            labs.sort(key=lambda l: l["resultado"])
            analitos.append({
                "nombre": nombre, "unidad": unidad, "n": len(filas),
                "evaluacion": "no_evaluada",
                "valor_asignado": None, "sd_robusta": None, "cv": None,
                "n_suficiente": len(filas) >= N_MINIMO,
                "referencia_descriptiva": {
                    "mediana": round(statistics.median(valores), 2),
                    "minimo": round(min(valores), 2),
                    "maximo": round(max(valores), 2),
                },
                "nota_sin_evaluar": nota_sin_evaluar,
                "laboratorios": labs,
            })
            continue

        spec = especificaciones.get(nombre)
        if not spec:
            sys.exit(f"ERROR: '{nombre}' no tiene ETa en especificaciones_desempeno.")

        # --- Analito por GRUPO DE PARES (X* por plataforma) -----------------
        if nombre in por_grupo_pares:
            grupos_filas = defaultdict(list)
            for f in filas:
                grupos_filas[f["plataforma"]].append(f)

            grupos, labs = [], []
            for g, gf in sorted(grupos_filas.items(), key=lambda kv: -len(kv[1])):
                if len(gf) >= N_MINIMO_GRUPO:
                    gx, gs, gcv = _stats([f["valor"] for f in gf])
                    dE = delta_e(spec, gx)
                    sigma_pt = dE / 3.0
                    grupos.append({
                        "nombre": g, "n": len(gf), "evaluado": True,
                        "valor_asignado": gx, "sd_robusta": gs, "cv": gcv,
                        "eta": _spec_publica(spec, dE), "sigma_pt": round(sigma_pt, 4),
                        "n_suficiente": len(gf) >= N_MINIMO,
                    })
                    for f in gf:
                        z = (f["valor"] - gx) / sigma_pt if sigma_pt else None
                        labs.append(_entrada(f, z, {"grupo": g}))
                else:
                    grupos.append({
                        "nombre": g, "n": len(gf), "evaluado": False,
                        "motivo": f"Grupo de pares insuficiente (n < {N_MINIMO_GRUPO})",
                    })
                    for f in gf:
                        labs.append(_entrada(f, None, {"grupo": g}))

            labs.sort(key=lambda l: (l["z_score"] is None, l["z_score"] or 0))
            for g in grupos:
                g["conteos"] = conteos_analito(
                    [l for l in labs if l.get("grupo") == g["nombre"]])

            gx_all, gs_all, cv_all = _stats([f["valor"] for f in filas])
            analitos.append({
                "nombre": nombre, "unidad": unidad, "n": len(filas),
                "evaluacion": "grupo_pares",
                "valor_asignado": gx_all, "sd_robusta": gs_all, "cv": cv_all,
                "grupos": grupos,
                "laboratorios": labs,
            })
            continue

        # --- Analito AGRUPADO (un X* para todos) ----------------------------
        x_star, s_star, cv = _stats([f["valor"] for f in filas])
        dE = delta_e(spec, x_star)
        sigma_pt = dE / 3.0
        labs = [_entrada(f, (f["valor"] - x_star) / sigma_pt if sigma_pt else None)
                for f in filas]
        labs.sort(key=lambda l: (l["z_score"] is None, l["z_score"] or 0))

        analitos.append({
            "nombre": nombre, "unidad": unidad, "n": len(filas),
            "evaluacion": "agrupada",
            "valor_asignado": x_star, "sd_robusta": s_star, "cv": cv,
            "eta": _spec_publica(spec, dE), "sigma_pt": round(sigma_pt, 4),
            "n_suficiente": len(filas) >= N_MINIMO,
            "laboratorios": labs,
        })
    return analitos


CRITERIOS = {
    "que_es_clia": "CLIA (Clinical Laboratory Improvement Amendments de 1988) es "
                   "la regulación federal de los Estados Unidos que establece los "
                   "estándares de calidad de los laboratorios clínicos. Entre ellos "
                   "fija el Error Total Permitido (ETa) por analito para los ensayos "
                   "de aptitud, codificado en 42 CFR §493. Es una de las referencias "
                   "internacionales admitidas por ISO 13528 e ISO/IEC 17043 para "
                   "definir criterios de aceptación por aptitud al uso.",
    "valor_asignado": "Media robusta (Algoritmo A, ISO 13528:2022).",
    "dispersion": "σ* (desviación robusta) y CV son informativos: muestran la "
                  "concordancia entre laboratorios; NO deciden la evaluación.",
    "evaluacion": "z-score con σpt = ETa/3. Por construcción, |z| = 3 equivale a "
                  "una desviación igual al Error Total Permitido (ETa), es decir, "
                  "al límite de aceptación de CLIA §493.931.",
    "niveles": [
        {"clasificacion": "A", "nombre": "Satisfactorio",    "regla": "|z| ≤ 2 (dentro de ⅔ del ETa)"},
        {"clasificacion": "C", "nombre": "Alerta",           "regla": "2 < |z| < 3 (entre ⅔ del ETa y el límite)"},
        {"clasificacion": "I", "nombre": "No satisfactorio", "regla": "|z| ≥ 3 (fuera del límite de CLIA)"},
    ],
    "eta_fuente": "Error Total Permitido de CLIA — 42 CFR §493.931 (regla final "
                  "CMS-3355-F, 2022). Lipasa y Bilirrubina Directa no están reguladas "
                  "por CLIA: se usa el ETa deseable por variación biológica (EFLM).",
}


def escribir_json(codigo, analitos, area="quimica"):
    tot = Counter()
    for a in analitos:
        tot.update(l["clasificacion"] for l in a["laboratorios"])

    # Copia saneada: fuera los campos internos (metodo/instrumento/plataforma
    # re-identifican al laboratorio) y se fija evaluacion_confiable=True — en el
    # modelo CLIA la σ no viene del consenso, así que no hay σ* inflada.
    limpios = []
    for a in analitos:
        limpios.append({
            **a,
            # Excepción: un analito que la ronda decidió no calificar tampoco
            # entra en el desempeño global ni en el resumen por laboratorio.
            # Ese es el efecto de evaluacion_confiable=False aguas abajo.
            "evaluacion_confiable": a.get("evaluacion") != "no_evaluada",
            "conteos": conteos_analito(a["laboratorios"]),
            "laboratorios": [
                {k: v for k, v in l.items() if k not in CAMPOS_INTERNOS}
                for l in a["laboratorios"]
            ],
        })
    analitos = limpios

    doc = {
        "codigo": codigo,
        "area": area,
        "modelo": "clia",
        "fecha": fecha_calculo(codigo),
        "metodologia": "Valor asignado: media robusta (ISO 13528, Algoritmo A). "
                       "Evaluación: z-score con σpt = ETa/3 (CLIA §493.931).",
        "evaluacion": "clia",
        "criterios_aceptacion": CRITERIOS,
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
    ruta = os.path.join(SALIDA_DIR, f"{codigo}-{area}-clia.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return ruta, tot


def main():
    ap = argparse.ArgumentParser(
        description="Evaluación por aptitud al uso (modelo CLIA) — pipeline paralelo.")
    ap.add_argument("--codigo", help="Código de ensayo (por defecto: ronda activa)")
    args = ap.parse_args()

    codigo = args.codigo
    if not codigo:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            codigo = json.load(f)["ronda_activa"]["codigo"]

    por_analito, _ceros = cargar(codigo)
    especificaciones = leer_especificaciones("quimica")
    por_grupo_pares = analitos_por_grupo_pares(codigo, "quimica")
    sin_eval, nota_sin_eval = analitos_sin_evaluar(codigo, "quimica")
    por_grupo_pares = por_grupo_pares - sin_eval
    if sin_eval and not nota_sin_eval:
        sys.exit("ERROR: hay analitos en 'sin_evaluar' pero falta "
                 "'sin_evaluar_nota' en config.json.")

    analitos = evaluar(por_analito, especificaciones, por_grupo_pares,
                       sin_evaluar=sin_eval, nota_sin_evaluar=nota_sin_eval)
    ruta, tot = escribir_json(codigo, analitos)

    evaluadas = tot["A"] + tot["C"] + tot["I"]
    print(f"\n  Evaluación CLIA (σpt = ETa/3) — {codigo}")
    print(f"  Escrito: {ruta}")
    print(f"  Evaluaciones: {evaluadas}   "
          f"A: {tot['A']} ({tot['A']/evaluadas*100:.1f}%)   "
          f"C: {tot['C']} ({tot['C']/evaluadas*100:.1f}%)   "
          f"I: {tot['I']} ({tot['I']/evaluadas*100:.1f}%)"
          + (f"   NE: {tot['NE']}" if tot["NE"] else ""))


if __name__ == "__main__":
    main()
