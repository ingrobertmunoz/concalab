"""
Orquestador del informe de Química Clínica: de Firestore a la página publicable.

Por qué existe
--------------
Las etapas eran cinco comandos sueltos cuyo orden solo vivía en CLAUDE.md. Eso
tiene dos problemas. El primero es de memoria: hay que recordar la secuencia una
vez al año. El segundo es más serio: nada impedía **saltarse una etapa**, y las
etapas no son opcionales. La auditoría de unidades no es informativa —existe
para no publicar como no conforme a un laboratorio que en realidad reportó en
otra unidad—, y la validación del contrato atrapa fallos que en el navegador son
silenciosos.

Este script encadena todo, se detiene en el primer error y deja explícitas las
COMPUERTAS MANUALES: los puntos donde la decisión es del proveedor del ensayo y
no puede automatizarse.

Lo que NO hace
--------------
No publica. La página `publicaciones/informes/<codigo>.html` se crea a mano
clonando la de la ronda anterior y apuntando su JSON_URL, y solo después de que
una persona revisó el informe preliminar. Automatizar ese paso convertiría un
juicio profesional en un efecto secundario.

Uso:
  conda activate concalab
  python scripts/informe_quimica.py                       # ronda activa
  python scripts/informe_quimica.py --codigo EA-001-2026
  python scripts/informe_quimica.py --desde calcular      # reusa el CSV ya extraído
  python scripts/informe_quimica.py --solo-verificar      # no recalcula, solo comprueba
"""

import os
import sys
import json
import time
import argparse
import subprocess

CONFIG_PATH = "data/config.json"
AREA = "quimica"

PY = sys.executable
BASE = os.path.dirname(os.path.abspath(__file__))

# Orden no negociable. Cada etapa es (clave, título, comando, obligatoria).
# 'extraer' es la única que toca la red; el resto trabaja sobre archivos.
ETAPAS = [
    ("extraer",  "Extraer de Firestore",        "extraer_resultados_firebase.py"),
    ("calcular", "Calcular Z-Score",            "calcular_zscore.py"),
    ("validar",  "Validar contrato JSON↔HTML",  "validar_informe.py"),
    ("auditar",  "Auditar unidades",            "auditar_unidades.py"),
    ("preliminar", "Informe preliminar",        "informe_preliminar.py"),
]


def ejecutar(script, codigo, mostrar_todo=False):
    """Corre una etapa. Devuelve (ok, salida)."""
    cmd = [PY, os.path.join(BASE, script), "--codigo", codigo]
    r = subprocess.run(cmd, capture_output=True, text=True)
    salida = (r.stdout or "") + (r.stderr or "")
    if mostrar_todo:
        print(salida)
    return r.returncode == 0, salida


def resumir(clave, salida):
    """Extrae de cada etapa la línea que de verdad importa."""
    lineas = [l.strip() for l in salida.splitlines() if l.strip()]

    def buscar(*fragmentos):
        for l in lineas:
            if any(f in l for f in fragmentos):
                return l
        return None

    if clave == "extraer":
        labs = buscar("Laboratorios:")
        quim = buscar("Filas Química:")
        if labs and quim:
            n_labs = labs.split(":")[-1].strip()
            n_quim = quim.split(":")[-1].strip()
            return f"{n_labs} laboratorios · {n_quim} filas de Química"
        return buscar("CSV escrito en") or "completado"
    if clave == "calcular":
        return buscar("Evaluaciones:") or "completado"
    if clave == "validar":
        return buscar("OK —", "ERROR") or "completado"
    if clave == "auditar":
        return buscar("Atribuibles a unidad") or "completado"
    if clave == "preliminar":
        return buscar("Informe preliminar:") or "completado"
    return "completado"


def avisos(salida):
    """Las líneas AVISO se propagan: son decisiones pendientes, no ruido."""
    return [l.strip() for l in salida.splitlines() if l.strip().startswith("AVISO")]


def main():
    ap = argparse.ArgumentParser(
        description="Encadena el pipeline del informe de Química Clínica.")
    ap.add_argument("--codigo", help="Código de ensayo (por defecto: ronda activa)")
    ap.add_argument("--desde", choices=[c for c, _, _ in ETAPAS],
                    help="Reanudar desde esta etapa (salta las anteriores)")
    ap.add_argument("--solo-verificar", action="store_true",
                    help="No recalcula: solo valida el contrato y audita unidades")
    ap.add_argument("--verboso", action="store_true", help="Muestra la salida completa")
    args = ap.parse_args()

    codigo = args.codigo
    if not codigo:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            codigo = json.load(f)["ronda_activa"]["codigo"]

    etapas = ETAPAS
    if args.solo_verificar:
        etapas = [e for e in ETAPAS if e[0] in ("validar", "auditar")]
    elif args.desde:
        i = [c for c, _, _ in ETAPAS].index(args.desde)
        etapas = ETAPAS[i:]

    print()
    print("=" * 74)
    print(f"  INFORME DE QUÍMICA CLÍNICA — {codigo}")
    print("=" * 74)

    pendientes = []
    t0 = time.time()

    for n, (clave, titulo, script) in enumerate(etapas, 1):
        etiqueta = f"  [{n}/{len(etapas)}] {titulo}"
        print(f"{etiqueta} {'.' * max(3, 42 - len(etiqueta))} ", end="", flush=True)

        ok, salida = ejecutar(script, codigo, args.verboso)
        if not ok:
            print("FALLÓ\n")
            print(salida)
            print("=" * 74)
            print(f"  Pipeline detenido en '{clave}'. Nada más se ejecutó.")
            print("=" * 74)
            sys.exit(1)

        print(resumir(clave, salida))
        pendientes += avisos(salida)

    print("=" * 74)

    if pendientes:
        print("\n  AVISOS QUE REQUIEREN DECISIÓN:")
        for a in dict.fromkeys(pendientes):
            print(f"    · {a}")

    # Las compuertas manuales son el punto del script: dejar visible lo que
    # ninguna automatización debe decidir por el proveedor del ensayo.
    print(f"""
  COMPUERTAS MANUALES antes de publicar:

    1. Revisar el informe preliminar de triaje:
         python3 -m http.server 8765
         http://localhost:8765/support/preliminar_{codigo}-{AREA}.html

    2. Decidir qué analitos van por grupo de pares y declararlo en
       {CONFIG_PATH} → decisiones_evaluacion.{codigo}.{AREA}.grupo_pares
       (si cambia algo, volver a correr desde 'calcular')

    3. Resolver los casos atípicos con el laboratorio cuando corresponda.

  PUBLICAR (a mano, después de lo anterior):

    Clonar la página de la ronda anterior y apuntar su JSON_URL a
      data/informes/{codigo}-{AREA}.json
    Registrar la tarjeta en publicaciones/informes.html
    Verificar sirviendo el sitio: python3 -m http.server 8765
""")
    print(f"  {len(etapas)} etapa(s) en {time.time() - t0:.1f}s")
    print("=" * 74)


if __name__ == "__main__":
    main()
