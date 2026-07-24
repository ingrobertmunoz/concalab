"""
Auditoría de unidades sobre los resultados no conformes — uso interno CONCALAB.

Responde una pregunta concreta antes de publicar un informe: ¿algún laboratorio
salió no conforme por haber reportado en otra unidad, y no por un desempeño
analítico deficiente?

Método
------
Para cada resultado clasificado C o I se calcula el factor que haría falta para
llevarlo al valor asignado de su grupo:

    factor = X* / resultado

Si ese factor coincide (dentro de una tolerancia) con una conversión real entre
unidades usadas en química clínica, el resultado es candidato a error de unidad
y no a falla analítica. Se contrastan tanto conversiones genéricas de escala
(x10, x100, x1000) como los factores específicos de cada analito
(mmol/L ↔ mg/dL, µmol/L ↔ mg/dL, g/L ↔ g/dL…).

Cada caso se clasifica en:
  ERROR DE UNIDAD PROBABLE  el factor coincide con una conversión Y la unidad
                            declarada es coherente con esa conversión
  REVISAR                   el factor coincide con una conversión, pero la
                            unidad declarada no la respalda (puede ser error de
                            transcripción, coma decimal o dilución)
  DESVIACIÓN ANALÍTICA      el factor no corresponde a ninguna conversión

Importante: la unidad NO entra en el cálculo del Z-Score (solo el número). Que
un laboratorio escriba mal la etiqueta no afecta su evaluación; lo que importa
es si el VALOR está en otra escala. Por eso el veredicto se apoya en el factor
y usa la etiqueta únicamente como confirmación.

Uso:
  conda activate concalab
  python scripts/auditar_unidades.py --codigo EA-001-2026
  python scripts/auditar_unidades.py --codigo EA-001-2026 --incluir-cuestionables
"""

import os
import sys
import json
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calcular_zscore import (  # noqa: E402
    cargar, calcular_agrupado, ANALITOS_POR_GRUPO_PARES, CONFIG_PATH,
)

# Tolerancia relativa para aceptar que un factor observado coincide con uno teórico.
TOL = 0.12

# Conversiones genéricas de escala: cubren mg/L↔mg/dL, g/L↔g/dL y comas decimales.
FACTORES_GENERICOS = {
    10:    "x10 (p. ej. mg/L → mg/dL, g/L → g/dL, o coma decimal corrida)",
    100:   "x100 (dos posiciones decimales)",
    1000:  "x1000 (p. ej. µg ↔ mg)",
}

# Conversiones específicas por analito: factor que convierte la unidad alterna a
# la unidad canónica del ensayo. Fuente: factores estándar de química clínica.
FACTORES_ANALITO = {
    "Glucosa":             {18.0: "mmol/L → mg/dL"},
    "Urea":                {6.0: "mmol/L → mg/dL (urea)", 2.8: "mmol/L → mg/dL (BUN)"},
    "Creatinina":          {0.0113: "µmol/L → mg/dL"},
    "Ácido Úrico":         {0.0168: "µmol/L → mg/dL"},
    "Colesterol":          {38.67: "mmol/L → mg/dL"},
    "Colesterol HDL":      {38.67: "mmol/L → mg/dL"},
    "Triglicéridos":       {88.5: "mmol/L → mg/dL"},
    "Calcio":              {4.008: "mmol/L → mg/dL"},
    "Magnesio":            {2.43: "mmol/L → mg/dL"},
    "Fósforo":             {3.097: "mmol/L → mg/dL"},
    "Hierro":              {5.587: "µmol/L → µg/dL"},
    "Bilirrubina Total":   {0.0585: "µmol/L → mg/dL"},
    "Bilirrubina Directa": {0.0585: "µmol/L → mg/dL"},
    "Proteínas Total":     {0.1: "g/L → g/dL"},
    "Albúmina":            {0.1: "g/L → g/dL"},
}

# Pistas textuales en la unidad declarada que respaldarían cada conversión.
PISTAS = {
    "mmol/L → mg/dL":      ("MMOL", "MOL/L"),
    "mmol/L → mg/dL (urea)": ("MMOL",),
    "mmol/L → mg/dL (BUN)":  ("MMOL",),
    "µmol/L → mg/dL":      ("UMOL", "µMOL", "MCMOL"),
    "µmol/L → µg/dL":      ("UMOL", "µMOL"),
    "g/L → g/dL":          ("G/L",),
}


def unidad_modal(labs_unidades):
    """Unidad canónica del analito: la forma normalizada más frecuente."""
    cont = defaultdict(int)
    for u in labs_unidades:
        k = u.strip().lower().replace(" ", "")
        if k and not k.isdigit():
            cont[k] += 1
    return max(cont, key=cont.get) if cont else "?"


def x_asignado(a, lab):
    """Valor asignado que le corresponde al laboratorio (su grupo si aplica)."""
    if a.get("evaluacion") == "grupo_pares":
        for g in a["grupos"]:
            if g["nombre"] == lab.get("grupo") and g["evaluado"]:
                return g["valor_asignado"]
        return None
    return a["valor_asignado"]


def buscar_conversion(analito, factor):
    """Devuelve (descripcion, factor_teorico) si el factor coincide con alguna."""
    candidatos = dict(FACTORES_GENERICOS)
    candidatos.update(FACTORES_ANALITO.get(analito, {}))
    # También el inverso: el laboratorio pudo reportar en la unidad más grande.
    for f, d in list(candidatos.items()):
        candidatos.setdefault(round(1 / f, 6), f"1/({d})")

    for f, desc in candidatos.items():
        if f and abs(factor - f) / f <= TOL:
            return desc, f
    return None, None


def unidad_respalda(unidad_raw, desc):
    u = (unidad_raw or "").upper().replace(" ", "")
    for clave, pistas in PISTAS.items():
        if clave in desc:
            return any(p in u for p in pistas)
    # Conversión genérica de escala: no hay pista textual que la confirme.
    return None


def auditar(analitos, incluir_c):
    clases = {"I", "C"} if incluir_c else {"I"}
    casos = []
    for a in analitos:
        canon = unidad_modal([l.get("unidad_raw", "") for l in a["laboratorios"]])
        for l in a["laboratorios"]:
            if l["clasificacion"] not in clases or l["z_score"] is None:
                continue
            x = x_asignado(a, l)
            if not x or not l["resultado"]:
                continue
            factor = x / l["resultado"]
            desc, f_teo = buscar_conversion(a["nombre"], factor)
            respalda = unidad_respalda(l.get("unidad_raw"), desc) if desc else None

            if desc and respalda:
                veredicto = "ERROR DE UNIDAD PROBABLE"
            elif desc:
                veredicto = "REVISAR"
            else:
                veredicto = "DESVIACIÓN ANALÍTICA"

            casos.append({
                "analito": a["nombre"], "unidad_canonica": canon,
                "lab": l["id"], "resultado": l["resultado"],
                "unidad_raw": l.get("unidad_raw", ""), "z": l["z_score"],
                "clasificacion": l["clasificacion"], "x_asignado": x,
                "factor": factor, "conversion": desc, "veredicto": veredicto,
            })
    return casos


def imprimir(casos, incluir_c):
    orden = {"ERROR DE UNIDAD PROBABLE": 0, "REVISAR": 1, "DESVIACIÓN ANALÍTICA": 2}
    casos.sort(key=lambda c: (orden[c["veredicto"]], c["analito"], c["lab"]))

    print("\n" + "=" * 100)
    print("  AUDITORÍA DE UNIDADES — ¿los no conformes lo son por unidad o por desempeño?")
    print(f"  Alcance: clasificación {'I y C' if incluir_c else 'I (no conformes)'}   ·   "
          f"casos analizados: {len(casos)}")
    print("=" * 100)

    for v in ("ERROR DE UNIDAD PROBABLE", "REVISAR", "DESVIACIÓN ANALÍTICA"):
        grupo = [c for c in casos if c["veredicto"] == v]
        print(f"\n  ── {v}  ({len(grupo)}) " + "─" * (72 - len(v)))
        if not grupo:
            print("      ninguno")
            continue
        if v == "DESVIACIÓN ANALÍTICA":
            print(f"      {'Lab':<6}{'Analito':<24}{'Resultado':>12} {'unidad':<10}"
                  f"{'X*':>10}{'z':>8}{'factor':>9}")
            for c in grupo:
                print(f"      {c['lab']:<6}{c['analito'][:23]:<24}{c['resultado']:>12g} "
                      f"{(c['unidad_raw'] or '—')[:9]:<10}{c['x_asignado']:>10g}"
                      f"{c['z']:>+8.1f}{c['factor']:>9.2f}")
            continue
        for c in grupo:
            print(f"      {c['lab']}  ·  {c['analito']}  ({c['clasificacion']}, z = {c['z']:+.1f})")
            print(f"          reportó {c['resultado']:g} {c['unidad_raw'] or '(sin unidad)'}"
                  f"   ·   X* del grupo = {c['x_asignado']:g} {c['unidad_canonica']}")
            print(f"          factor necesario {c['factor']:.3f}  ≈  {c['conversion']}")
            corregido = c["resultado"] * c["factor"]
            print(f"          convertido daría ≈ {corregido:g} {c['unidad_canonica']} "
                  f"(coincidiría con el consenso)")

    print("\n" + "=" * 100)
    n_u = sum(1 for c in casos if c["veredicto"] == "ERROR DE UNIDAD PROBABLE")
    n_r = sum(1 for c in casos if c["veredicto"] == "REVISAR")
    n_d = sum(1 for c in casos if c["veredicto"] == "DESVIACIÓN ANALÍTICA")
    print(f"  Atribuibles a unidad: {n_u}   ·   a revisar: {n_r}   ·   desempeño analítico: {n_d}")
    print("  La unidad no entra en el cálculo del Z-Score: solo importa si el VALOR está en otra")
    print("  escala. Una etiqueta mal escrita con el valor correcto no afecta la evaluación.")
    print("=" * 100)


def main():
    ap = argparse.ArgumentParser(description="Audita si los no conformes lo son por unidad.")
    ap.add_argument("--codigo")
    ap.add_argument("--incluir-cuestionables", action="store_true")
    args = ap.parse_args()

    codigo = args.codigo
    if not codigo:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            codigo = json.load(f)["ronda_activa"]["codigo"]

    por_analito, _ = cargar(codigo)
    analitos = calcular_agrupado(por_analito, por_grupo_pares=ANALITOS_POR_GRUPO_PARES)

    # El cálculo no arrastra la unidad cruda; se reincorpora aquí para el veredicto.
    crudo = {(f["cod"], nom): f["unidad"] for nom, fs in por_analito.items() for f in fs}
    for a in analitos:
        for l in a["laboratorios"]:
            l["unidad_raw"] = crudo.get((l["id"], a["nombre"]), "")

    imprimir(auditar(analitos, args.incluir_cuestionables), args.incluir_cuestionables)


if __name__ == "__main__":
    main()
