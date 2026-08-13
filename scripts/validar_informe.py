"""
Valida el contrato entre el JSON calculado y la página HTML del informe.

Por qué existe
--------------
La página pública no se genera: es un armazón estático que hace `fetch` del
JSON y dibuja todo con Plotly en el navegador. El acoplamiento entre Python y
JavaScript son nombres de campo comparados como texto, y **JavaScript no falla
cuando un campo no existe**: `a.evaluacion_confiable` sobre un objeto que no lo
trae devuelve `undefined`, que es falsy, y la página sigue dibujando.

Eso hace que el modo de fallo sea silencioso y peligroso en la dirección
equivocada. Si `escribir_json` dejara de emitir `evaluacion_confiable`, los
analitos no concluyentes se presentarían como desempeño normal: exactamente el
falso negativo que la evaluación por grupo de pares existe para evitar.

Este validador corre después de calcular y antes de publicar. Comprueba tres
cosas distintas:

  1. ESTRUCTURA   están todos los campos que el JS lee, con el tipo correcto.
  2. SEMÁNTICA    los valores son coherentes entre sí (un NE no puede traer
                  Z-Score, un grupo evaluado no puede venir sin valor asignado).
  3. ANONIMATO    no se filtró nada que permita re-identificar a un laboratorio.

La lista CAMPOS_* se extrajo leyendo los accesos reales del JS de la página.
Si la página empieza a leer un campo nuevo, hay que agregarlo aquí.

Uso:
  python scripts/validar_informe.py --codigo EA-001-2026
  python scripts/validar_informe.py --codigo EA-001-2026 --area quimica
"""

import os
import re
import sys
import json
import argparse

SALIDA_DIR  = os.path.join("data", "informes")
CONFIG_PATH = "data/config.json"

# Campos que el JS de la página lee en cada nivel.
CAMPOS_RAIZ    = ("codigo", "fecha", "area", "analitos", "resumen")
CAMPOS_ANALITO = ("nombre", "n", "unidad", "evaluacion",
                  "evaluacion_confiable", "laboratorios")
CAMPOS_LAB     = ("id", "resultado", "z_score", "clasificacion")
CAMPOS_GRUPO   = ("nombre", "n", "evaluado")

# El X*, la σ* y el CV viven en distinto nivel según cómo se evaluó el analito:
# agrupado tiene un centro único; por grupo de pares tiene uno por plataforma y
# el JS los lee de `g`, no de `a` (esPorPares() corta antes de tocar a.cv).
CAMPOS_AGRUPADO   = ("valor_asignado", "sd_robusta", "cv")
CAMPOS_POR_GRUPOS = ("valor_asignado", "sd_robusta", "cv")

# Nunca deben aparecer en el JSON desplegado: identifican al laboratorio.
#
# 'cod_interno' salió de esta lista en EA-001-2026, cuando el proveedor lo declaró
# identificador público de la ronda (ver identificador_publico en data/config.json).
# Aun así no puede viajar como campo crudo: solo se publica formateado como etiqueta
# en 'id', que FORMATO_COD verifica.
CAMPOS_PROHIBIDOS = {
    "metodo", "instrumento", "plataforma", "laboratorio", "correo",
    "representante", "telefono", "uid_lab", "unidad_raw",
}

# Marcas de equipo: revelan qué analizador usa cada cod_anonimo. En un grupo
# pequeño eso basta para re-identificar al laboratorio en un mercado local.
MARCAS = ("fujifilm", "vitros", "dri-chem", "dirui", "mindray", "humastar",
          "biosystems", "architect", "bioclin", "wiener", "urit", "prietest")

CLASIFICACIONES = {"A", "C", "I", "NE"}
# Formatos admitidos de identificador público. 'L-NNN' es el de EA-001-2026 en
# adelante; el de 2 letras + dígito se conserva porque las rondas ya publicadas
# mantienen el identificador con el que se entregaron y deben seguir validando.
# El relleno a 3 dígitos es obligatorio: las tablas y el heatmap ordenan como texto.
FORMATO_COD = re.compile(r"^(L-\d{3}|[A-Z]{2}\d)$")


class Validador:
    def __init__(self):
        self.errores = []
        self.avisos = []

    def error(self, msg):
        self.errores.append(msg)

    def aviso(self, msg):
        self.avisos.append(msg)

    # ── 1. Estructura ────────────────────────────────────────────────────
    def estructura(self, d):
        for c in CAMPOS_RAIZ:
            if c not in d:
                self.error(f"falta el campo raíz '{c}'")
        if not isinstance(d.get("analitos"), list) or not d["analitos"]:
            self.error("'analitos' debe ser una lista no vacía")
            return

        for a in d["analitos"]:
            nom = a.get("nombre", "(sin nombre)")
            for c in CAMPOS_ANALITO:
                if c not in a:
                    self.error(f"{nom}: falta '{c}'")

            if not isinstance(a.get("laboratorios"), list) or not a["laboratorios"]:
                self.error(f"{nom}: 'laboratorios' debe ser una lista no vacía")
                continue

            for l in a["laboratorios"]:
                for c in CAMPOS_LAB:
                    if c not in l:
                        self.error(f"{nom}/{l.get('id','?')}: falta '{c}'")

            if a.get("evaluacion") == "no_evaluada":
                # Un analito sin calificar NO debe traer valor asignado: publicar
                # un X* mientras se declara que no hay consenso defendible es
                # justamente la contradicción que la decisión evita.
                for c in ("valor_asignado", "sd_robusta", "cv"):
                    if a.get(c) is not None:
                        self.error(f"{nom}: no evaluado pero publica '{c}'")
                if not a.get("nota_sin_evaluar"):
                    self.error(f"{nom}: no evaluado sin 'nota_sin_evaluar' que lo explique")
                if a.get("evaluacion_confiable") is not False:
                    self.error(f"{nom}: no evaluado debe traer evaluacion_confiable=false "
                               f"para quedar fuera del desempeño global")
                for l in a["laboratorios"]:
                    if l.get("clasificacion") != "NE":
                        self.error(f"{nom}/{l.get('id')}: analito no evaluado con "
                                   f"clasificación '{l.get('clasificacion')}'")
            elif a.get("evaluacion") == "grupo_pares":
                if not isinstance(a.get("grupos"), list) or not a["grupos"]:
                    self.error(f"{nom}: evaluación por grupo de pares sin 'grupos'")
                    continue
                for g in a["grupos"]:
                    for c in CAMPOS_GRUPO:
                        if c not in g:
                            self.error(f"{nom}/grupo {g.get('nombre','?')}: falta '{c}'")
                    # Solo los grupos evaluados aportan estadística; los que no
                    # llegan al mínimo se revisan en semantica().
                    if g.get("evaluado"):
                        for c in CAMPOS_POR_GRUPOS:
                            if c not in g:
                                self.error(f"{nom}/grupo {g.get('nombre','?')}: falta '{c}'")
            else:
                for c in CAMPOS_AGRUPADO:
                    if c not in a:
                        self.error(f"{nom}: evaluación agrupada sin '{c}'")

    # ── 2. Semántica ─────────────────────────────────────────────────────
    def semantica(self, d):
        for a in d.get("analitos", []):
            nom = a.get("nombre", "?")
            por_pares = a.get("evaluacion") == "grupo_pares"

            # Un grupo evaluado necesita centro y dispersión; uno no evaluado
            # debe declarar por qué, o el informe no puede explicar los NE.
            for g in a.get("grupos", []) or []:
                if g.get("evaluado"):
                    for c in ("valor_asignado", "sd_robusta", "cv"):
                        if g.get(c) is None:
                            self.error(f"{nom}/grupo {g.get('nombre')}: evaluado sin '{c}'")
                elif not g.get("motivo"):
                    self.error(f"{nom}/grupo {g.get('nombre')}: no evaluado sin 'motivo'")

            nombres_grupo = {g.get("nombre") for g in (a.get("grupos") or [])}
            vistos = set()

            for l in a.get("laboratorios", []):
                cod, clas, z = l.get("id"), l.get("clasificacion"), l.get("z_score")

                if not FORMATO_COD.match(str(cod or "")):
                    self.error(f"{nom}: identificador '{cod}' no tiene un formato público válido")
                if cod in vistos:
                    self.error(f"{nom}: el laboratorio {cod} aparece dos veces")
                vistos.add(cod)

                if clas not in CLASIFICACIONES:
                    self.error(f"{nom}/{cod}: clasificación '{clas}' desconocida")

                # NE y Z-Score son mutuamente excluyentes: un laboratorio sin
                # grupo de pares suficiente no tiene contra qué compararse.
                if clas == "NE" and z is not None:
                    self.error(f"{nom}/{cod}: clasificado NE pero trae z_score={z}")
                if clas != "NE" and z is None:
                    self.error(f"{nom}/{cod}: clasificado {clas} sin z_score")

                # Coherencia entre |z| y la clasificación (ISO 13528 §9).
                if z is not None and clas in ("A", "C", "I"):
                    esperada = "A" if abs(z) <= 2 else ("C" if abs(z) < 3 else "I")
                    if esperada != clas:
                        self.error(f"{nom}/{cod}: z={z} debería clasificar {esperada}, "
                                   f"no {clas}")

                # Un 0 nunca es una medición en química clínica cuantitativa.
                if l.get("resultado") == 0:
                    self.error(f"{nom}/{cod}: resultado 0 en el JSON publicado "
                               f"(debería excluirse como 'no reportado')")

                if por_pares:
                    if l.get("grupo") is None:
                        self.error(f"{nom}/{cod}: analito por grupo de pares sin 'grupo'")
                    elif l["grupo"] not in nombres_grupo:
                        self.error(f"{nom}/{cod}: grupo '{l['grupo']}' no está en 'grupos'")

            n_declarado = a.get("n")
            if isinstance(n_declarado, int) and n_declarado != len(a.get("laboratorios", [])):
                self.error(f"{nom}: n={n_declarado} no coincide con "
                           f"{len(a['laboratorios'])} laboratorios")

            # Un CV muy alto sin declararse no concluyente se publicaría como
            # desempeño normal aunque la σ* esté inflada. En un analito ya
            # evaluado por grupo de pares el CV global alto es justamente lo
            # esperado —es el motivo de haberlo separado—, así que ahí se mira
            # el CV de cada grupo, que sí debe haber bajado.
            if por_pares:
                for g in a.get("grupos", []) or []:
                    if g.get("evaluado") and (g.get("cv") or 0) > 40:
                        self.aviso(f"{nom}/grupo {g.get('nombre')}: CV {g['cv']}% alto "
                                   f"pese a la separación por plataforma")
            elif (a.get("cv") or 0) > 40 and a.get("evaluacion_confiable") is not False:
                self.aviso(f"{nom}: CV {a['cv']}% muy alto y marcado como concluyente "
                           f"— revisar si corresponde grupo de pares")

    # ── 2b. Métricas derivadas ───────────────────────────────────────────
    def metricas(self, d):
        """
        Recalcula desde analitos[] las cifras que el informe presenta como
        conclusión y falla si no cuadran.

        Sin esto la métrica titular sería un número sin respaldo: el JSON
        podría declarar 54.1% de conformidad mientras los Z-Score dicen otra
        cosa, y nada lo detectaría. Publicar una conclusión que la estadística
        no sostiene es peor que no publicarla.
        """
        # Conteos por analito.
        for a in d.get("analitos", []):
            c = a.get("conteos")
            if not c:
                self.error(f"{a.get('nombre','?')}: falta 'conteos'")
                continue
            real = {"A": 0, "C": 0, "I": 0, "NE": 0}
            for l in a.get("laboratorios", []):
                if l.get("clasificacion") in real:
                    real[l["clasificacion"]] += 1
            for k, v in real.items():
                if c.get(k) != v:
                    self.error(f"{a.get('nombre','?')}: conteos.{k}={c.get(k)} "
                               f"pero hay {v} laboratorios así clasificados")

            # % dentro del criterio: (A+C) sobre los evaluados. Se recalcula
            # aquí porque el PDF ordena su consolidado por analito con esta
            # cifra: si viniera mal, la tabla presentaría como mejor analito
            # uno que no lo es, y nada lo detectaría.
            n = real["A"] + real["C"] + real["I"]
            esperado = round((real["A"] + real["C"]) / n * 100, 1) if n else None
            if c.get("pct_dentro") != esperado:
                self.error(f"{a.get('nombre','?')}: conteos.pct_dentro="
                           f"{c.get('pct_dentro')} pero debería ser {esperado}")

        # Resumen global.
        r = d.get("resumen") or {}
        tot = {"A": 0, "C": 0, "I": 0, "NE": 0}
        for a in d.get("analitos", []):
            for l in a.get("laboratorios", []):
                if l.get("clasificacion") in tot:
                    tot[l["clasificacion"]] += 1
        for campo, esperado in (("aceptables", tot["A"]), ("cuestionables", tot["C"]),
                                ("inaceptables", tot["I"]), ("sin_evaluar", tot["NE"]),
                                ("total", tot["A"] + tot["C"] + tot["I"])):
            if r.get(campo) != esperado:
                self.error(f"resumen.{campo}={r.get(campo)} pero el recálculo da {esperado}")

        # Desempeño global: se recalcula con la misma regla que el informe
        # declara, incluida la exclusión de analitos no concluyentes.
        g = d.get("desempeno_global")
        if not g:
            self.error("falta 'desempeno_global'")
            return

        por_lab = {}
        for a in d.get("analitos", []):
            if a.get("evaluacion_confiable") is False:
                continue
            for l in a.get("laboratorios", []):
                s = por_lab.setdefault(l.get("id"), {"A": 0, "C": 0, "I": 0})
                if l.get("clasificacion") in s:
                    s[l["clasificacion"]] += 1

        total = len(por_lab)
        conformes = sum(1 for s in por_lab.values() if s["I"] == 0)

        if g.get("laboratorios") != total:
            self.error(f"desempeno_global.laboratorios={g.get('laboratorios')} "
                       f"pero el recálculo da {total}")
        if g.get("conformes") != conformes:
            self.error(f"desempeno_global.conformes={g.get('conformes')} "
                       f"pero el recálculo da {conformes}")

        pct = round(conformes / total * 100, 1) if total else 0.0
        if g.get("pct_conformes") != pct:
            self.error(f"desempeno_global.pct_conformes={g.get('pct_conformes')} "
                       f"pero el recálculo da {pct}")

        # Los estratos deben cubrir a todos los laboratorios sin solaparse: si
        # no suman el total, algún laboratorio quedó fuera de la clasificación.
        suma = 0
        for e in g.get("estratos", []):
            hasta = e.get("hasta")
            dentro = [s for s in por_lab.values()
                      if s["I"] >= e.get("desde", 0) and (hasta is None or s["I"] <= hasta)]
            if e.get("laboratorios") != len(dentro):
                self.error(f"estrato '{e.get('clave')}': declara {e.get('laboratorios')} "
                           f"laboratorios pero el recálculo da {len(dentro)}")
            suma += e.get("laboratorios") or 0
        if g.get("estratos") and suma != total:
            self.error(f"los estratos suman {suma} laboratorios pero hay {total}: "
                       f"los cortes dejan huecos o se solapan")

        # El primer estrato debe coincidir con los conformes, o el titular y la
        # estratificación estarían contando cosas distintas.
        primero = (g.get("estratos") or [{}])[0]
        if primero.get("laboratorios") not in (None, conformes):
            self.error(f"el estrato '{primero.get('clave')}' declara "
                       f"{primero['laboratorios']} pero hay {conformes} conformes")

    # ── 3. Anonimato ─────────────────────────────────────────────────────
    def anonimato(self, d, crudo):
        def recorrer(o, ruta=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in CAMPOS_PROHIBIDOS:
                        self.error(f"campo identificable '{k}' en {ruta or 'raíz'}")
                    recorrer(v, f"{ruta}.{k}")
            elif isinstance(o, list):
                for i, x in enumerate(o):
                    recorrer(x, f"{ruta}[{i}]")

        recorrer(d)

        bajo = crudo.lower()
        for marca in MARCAS:
            if marca in bajo:
                self.error(f"marca de equipo '{marca}' presente en el JSON desplegado")

    # ── 4. Modelo CLIA ───────────────────────────────────────────────────
    # Solo corre cuando el JSON declara modelo="clia". Verifica lo que el
    # modelo de consenso no tiene: que la σ de evaluación sea el ETa/3 y que el
    # z-score se reproduzca desde X* y σpt. Sin esto, un σpt mal calculado
    # pasaría —la coherencia |z|↔clasificación seguiría cuadrando— y el informe
    # calificaría contra un límite equivocado.
    def _especificaciones(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return (json.load(f).get("especificaciones_desempeno") or {}).get("quimica", {})
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _delta_e_cfg(spec, x):
        cand = []
        if spec.get("pct") is not None:
            cand.append(spec["pct"] / 100.0 * abs(x))
        if spec.get("abs") is not None:
            cand.append(float(spec["abs"]))
        return max(cand) if cand else None

    def _bloque_clia(self, etiqueta, bloque, spec_cfg, labs):
        eta, sigma_pt = bloque.get("eta"), bloque.get("sigma_pt")
        x = bloque.get("valor_asignado")
        if not eta or eta.get("delta_e") is None:
            self.error(f"{etiqueta}: evaluado sin 'eta.delta_e'"); return
        if sigma_pt is None:
            self.error(f"{etiqueta}: evaluado sin 'sigma_pt'"); return
        dE = eta["delta_e"]
        if abs(sigma_pt - dE / 3) > 0.01:
            self.error(f"{etiqueta}: sigma_pt={sigma_pt} ≠ δE/3={round(dE/3, 4)}")
        if spec_cfg and x is not None:
            dE_cfg = self._delta_e_cfg(spec_cfg, x)
            if dE_cfg is not None and abs(dE - dE_cfg) > 0.01:
                self.error(f"{etiqueta}: δE={dE} no coincide con config "
                           f"({round(dE_cfg, 4)}) sobre X*={x}")
        for l in labs:
            z, r = l.get("z_score"), l.get("resultado")
            if z is None or x is None or not sigma_pt:
                continue
            z_calc = (r - x) / sigma_pt
            # Tolerancia relativa: X* y σpt viajan redondeados en el JSON, y con
            # un |z| grande (errores gruesos) ese redondeo se amplifica. Un z mal
            # calculado de verdad se desvía mucho más que esto.
            if abs(z - z_calc) > max(0.05, abs(z_calc) * 0.0005):
                self.error(f"{etiqueta}/{l.get('id')}: z={z} no se reproduce desde "
                           f"X*={x}, σpt={sigma_pt} (da {round(z_calc, 2)})")

    def clia(self, d):
        esp = self._especificaciones()
        if "criterios_aceptacion" not in d:
            self.error("modelo clia sin 'criterios_aceptacion' (el panel de criterios)")
        for a in d.get("analitos", []):
            nom = a.get("nombre", "?")
            # Un analito que la ronda decidió no calificar no aplica ningún
            # criterio de aceptación: exigirle ETa obligaría a declarar un
            # límite que no se usa. estructura() ya comprueba su coherencia.
            if a.get("evaluacion") == "no_evaluada":
                continue
            spec_cfg = esp.get(nom)
            if spec_cfg is None:
                self.error(f"{nom}: sin ETa en config.especificaciones_desempeno.quimica")
            if a.get("evaluacion") == "grupo_pares":
                for g in a.get("grupos", []):
                    if g.get("evaluado"):
                        labs = [l for l in a.get("laboratorios", [])
                                if l.get("grupo") == g.get("nombre")]
                        self._bloque_clia(f"{nom}/grupo {g.get('nombre')}", g, spec_cfg, labs)
            else:
                self._bloque_clia(nom, a, spec_cfg, a.get("laboratorios", []))

    def informar(self, ruta):
        print("=" * 78)
        print(f"  VALIDACIÓN DEL CONTRATO JSON ↔ INFORME HTML")
        print(f"  {ruta}")
        print("=" * 78)

        for a in self.avisos:
            print(f"  AVISO   {a}")
        for e in self.errores:
            print(f"  ERROR   {e}")

        if not self.errores:
            print(f"  OK — estructura, semántica y anonimato correctos"
                  + (f" ({len(self.avisos)} aviso(s))" if self.avisos else ""))
        print("=" * 78)
        return not self.errores


def validar(codigo, area="quimica", modelo=None):
    sufijo = "-clia" if modelo == "clia" else ""
    ruta = os.path.join(SALIDA_DIR, f"{codigo}-{area}{sufijo}.json")
    if not os.path.exists(ruta):
        script = "evaluar_clia.py" if modelo == "clia" else "calcular_zscore.py"
        sys.exit(f"ERROR: no existe {ruta}\n"
                 f"Ejecuta primero: python scripts/{script} --codigo {codigo}")

    with open(ruta, encoding="utf-8") as f:
        crudo = f.read()
    d = json.loads(crudo)

    v = Validador()
    v.estructura(d)
    v.semantica(d)
    v.metricas(d)
    if d.get("modelo") == "clia":
        v.clia(d)
    v.anonimato(d, crudo)
    return v, ruta


def main():
    ap = argparse.ArgumentParser(description="Valida el JSON de un informe antes de publicarlo.")
    ap.add_argument("--codigo")
    ap.add_argument("--area", default="quimica")
    ap.add_argument("--modelo", choices=["consenso", "clia"], default="consenso",
                    help="'clia' valida el JSON -clia.json (evaluación por ETa)")
    args = ap.parse_args()

    codigo = args.codigo
    if not codigo:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            codigo = json.load(f)["ronda_activa"]["codigo"]

    v, ruta = validar(codigo, args.area, args.modelo)
    sys.exit(0 if v.informar(ruta) else 1)


if __name__ == "__main__":
    main()
