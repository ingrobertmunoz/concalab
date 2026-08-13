"""
Actualización puntual de laboratorios en Firebase (Auth + Firestore).

A diferencia de `importar_labs_firebase.py` (que recorre TODO el Excel y usa
.set() sobre cada doc), este script solo toca los laboratorios listados en el
archivo de operaciones, sin alterar el resto. Maneja estos casos:

  - "crear"            → nuevo lab: create_user en Auth + doc en Firestore.
  - "cambiar_correo"   → lab existente: localiza el usuario por cod_interno en
                         Firestore, actualiza el email en Auth y el campo
                         'correo' en Firestore. NO duplica el usuario.
  - "cambiar_datos"    → actualiza campos de Firestore (nombre, representante,
                         telefono, cod_anonimo...). Solo toca lo que incluyas.
  - "cambiar_password" → actualiza la contraseña del usuario en Auth.
  - "desactivar"       → habilita/deshabilita el login en Auth (disabled) y el
                         campo 'activo' en Firestore. Usa "activo": True/False.

Requisitos:
  conda activate concalab
  pip install firebase-admin

Las operaciones NO viven en este archivo: se leen de un JSON local
(support/operaciones_labs.json, ignorado por git). Ver `cargar_operaciones`.

Uso:
  python scripts/actualizar_labs_firebase.py --dry-run   # simula, no escribe
  python scripts/actualizar_labs_firebase.py             # escribe en Firebase
  python scripts/actualizar_labs_firebase.py --operaciones otra/ruta.json
"""

import sys
import os
import json
import argparse
import firebase_admin
from firebase_admin import credentials, auth, firestore

CREDS_PATH = "support/concalab-uasd-64ff4-firebase-adminsdk-fbsvc-c400cdf10b.json"
OPERACIONES_PATH = "support/operaciones_labs.json"
PLANTILLA_PATH = "support/operaciones_labs.ejemplo.json"


def cargar_operaciones(ruta):
    """Lee las operaciones de un JSON local, nunca del código.

    Antes eran una constante `OPERACIONES` dentro de este archivo, y eso era
    incompatible con que el repositorio sea público: una operación real lleva
    el `cod_interno` del laboratorio junto a su nombre y su correo, y desde
    EA-001-2026 el `cod_interno` ES el identificador que se publica en los
    informes (L-087, L-090...). Commitear el script con datos dentro habría
    permitido cruzar `L-087` con el nombre del laboratorio y de-anonimizar su
    desempeño — justamente el supuesto que `identificador_publico` da por
    cierto en data/config.json.

    Con el dato fuera del código, el registro de qué se cambió y cuándo se
    conserva (el JSON es un archivo de trabajo, no algo que haya que borrar
    después de correr el script), pero vive donde ya viven el Excel maestro y
    la clave de servicio: en support/, fuera del repositorio.
    """
    if not os.path.exists(ruta):
        print(f"\n  No existe {ruta} — no hay operaciones que aplicar.")
        print(f"  Para crearlo, copia la plantilla y edítala:")
        print(f"      cp {PLANTILLA_PATH} {ruta}\n")
        return []

    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)

    # Se admite tanto una lista suelta como el objeto con metadatos de la
    # plantilla; las claves que empiezan por '_' son documentación.
    ops = datos.get("operaciones", []) if isinstance(datos, dict) else datos

    validas = {"crear", "cambiar_correo", "cambiar_datos", "cambiar_password",
               "desactivar"}
    for i, op in enumerate(ops, 1):
        if op.get("accion") not in validas:
            sys.exit(f"\n  ERROR en {ruta}, operación {i}: acción "
                     f"{op.get('accion')!r} no reconocida.\n"
                     f"  Válidas: {', '.join(sorted(validas))}\n")
        if "cod_interno" not in op:
            sys.exit(f"\n  ERROR en {ruta}, operación {i}: falta 'cod_interno'.\n")
    return ops


def inicializar(dry_run):
    if dry_run:
        print("  [DRY-RUN] Firebase no inicializado — solo simulación.\n")
        return None, None
    cred = credentials.Certificate(CREDS_PATH)
    firebase_admin.initialize_app(cred)
    return auth, firestore.client()


def buscar_por_cod_interno(db, cod_interno):
    """Devuelve (doc_id, data) del lab con ese cod_interno, o (None, None)."""
    docs = list(
        db.collection("laboratorios").where("cod_interno", "==", cod_interno).stream()
    )
    if not docs:
        return None, None
    if len(docs) > 1:
        print(f"       ⚠ ATENCIÓN: {len(docs)} documentos con cod_interno={cod_interno}")
    d = docs[0]
    return d.id, d.to_dict()


def crear(auth_c, db, op, dry_run):
    print(f"\n[CREAR {op['cod_interno']}] {op['nombre']}")
    print(f"       Correo: {op['correo']} | Anónimo: {op['cod_anonimo']} | Pass: {op['password']}")
    if dry_run:
        print("       → [DRY-RUN] Se crearía en Auth + Firestore")
        return True

    correo = op["correo"].lower()
    try:
        usuario = auth_c.create_user(
            email=correo,
            password=op["password"],
            display_name=op["nombre"],
            disabled=not op["activo"],
        )
        uid = usuario.uid
        print(f"       ✓ Auth creado — uid: {uid}")
    except auth_c._auth_utils.EmailAlreadyExistsError:
        uid = auth_c.get_user_by_email(correo).uid
        print(f"       ⚠ Auth ya existía — uid: {uid} (se actualiza Firestore)")
    except Exception as e:
        print(f"       ✗ Error Auth: {e}")
        return False

    try:
        db.collection("laboratorios").document(uid).set({
            "uid": uid,
            "cod_interno": op["cod_interno"],
            "cod_anonimo": op["cod_anonimo"],
            "nombre": op["nombre"],
            "representante": op["representante"],
            "telefono": op["telefono"],
            "correo": correo,
            "activo": op["activo"],
            "creado_en": firestore.SERVER_TIMESTAMP,
        })
        print(f"       ✓ Firestore — doc: {uid[:12]}...")
        return True
    except Exception as e:
        print(f"       ✗ Error Firestore: {e}")
        return False


def cambiar_correo(auth_c, db, op, dry_run):
    cod = op["cod_interno"]
    nuevo = op["correo_nuevo"].lower()
    print(f"\n[CAMBIAR CORREO {cod}] → {nuevo}")
    if dry_run:
        print("       → [DRY-RUN] Se buscaría el lab por cod_interno y se actualizaría Auth + Firestore")
        return True

    doc_id, data = buscar_por_cod_interno(db, cod)
    if not doc_id:
        print(f"       ✗ No se encontró lab con cod_interno={cod} en Firestore")
        return False

    uid = data.get("uid", doc_id)
    actual = data.get("correo", "(desconocido)")
    print(f"       Lab: {data.get('nombre', '?')} | uid: {uid}")
    print(f"       Correo actual: {actual} → nuevo: {nuevo}")

    try:
        auth_c.update_user(uid, email=nuevo)
        print(f"       ✓ Auth email actualizado")
    except Exception as e:
        print(f"       ✗ Error Auth: {e}")
        return False

    try:
        db.collection("laboratorios").document(doc_id).update({"correo": nuevo})
        print(f"       ✓ Firestore campo 'correo' actualizado")
        return True
    except Exception as e:
        print(f"       ✗ Error Firestore: {e}")
        return False


def cambiar_datos(auth_c, db, op, dry_run):
    cod = op["cod_interno"]
    campos = op["campos"]
    print(f"\n[CAMBIAR DATOS {cod}] {campos}")
    if dry_run:
        print("       → [DRY-RUN] Se actualizarían esos campos en Firestore")
        return True

    doc_id, data = buscar_por_cod_interno(db, cod)
    if not doc_id:
        print(f"       ✗ No se encontró lab con cod_interno={cod} en Firestore")
        return False

    try:
        db.collection("laboratorios").document(doc_id).update(campos)
        print(f"       ✓ Firestore actualizado ({data.get('nombre', '?')})")
        # Si cambió el nombre, refleja también el display_name en Auth.
        if "nombre" in campos:
            auth_c.update_user(data.get("uid", doc_id), display_name=campos["nombre"])
            print(f"       ✓ Auth display_name actualizado")
        return True
    except Exception as e:
        print(f"       ✗ Error: {e}")
        return False


def cambiar_password(auth_c, db, op, dry_run):
    cod = op["cod_interno"]
    print(f"\n[CAMBIAR PASSWORD {cod}] → {op['password_nuevo']}")
    if dry_run:
        print("       → [DRY-RUN] Se actualizaría la contraseña en Auth")
        return True

    doc_id, data = buscar_por_cod_interno(db, cod)
    if not doc_id:
        print(f"       ✗ No se encontró lab con cod_interno={cod} en Firestore")
        return False
    try:
        auth_c.update_user(data.get("uid", doc_id), password=op["password_nuevo"])
        print(f"       ✓ Auth password actualizado ({data.get('nombre', '?')})")
        print(f"       ↳ Recuerda enviar la nueva contraseña al lab por correo.")
        return True
    except Exception as e:
        print(f"       ✗ Error Auth: {e}")
        return False


def desactivar(auth_c, db, op, dry_run):
    cod = op["cod_interno"]
    activo = op["activo"]
    estado = "REACTIVAR" if activo else "DESACTIVAR"
    print(f"\n[{estado} {cod}]")
    if dry_run:
        print(f"       → [DRY-RUN] Se pondría disabled={not activo} en Auth y activo={activo} en Firestore")
        return True

    doc_id, data = buscar_por_cod_interno(db, cod)
    if not doc_id:
        print(f"       ✗ No se encontró lab con cod_interno={cod} en Firestore")
        return False
    try:
        auth_c.update_user(data.get("uid", doc_id), disabled=not activo)
        db.collection("laboratorios").document(doc_id).update({"activo": activo})
        print(f"       ✓ {data.get('nombre', '?')} → activo={activo} (Auth + Firestore)")
        return True
    except Exception as e:
        print(f"       ✗ Error: {e}")
        return False


def main(dry_run, ruta_ops):
    print("=" * 60)
    print(f"  CONCALAB — Actualización puntual de labs {'(DRY-RUN)' if dry_run else ''}")
    print("=" * 60)

    operaciones = cargar_operaciones(ruta_ops)
    if not operaciones:
        return
    print(f"  Operaciones leídas de {ruta_ops}: {len(operaciones)}")

    auth_c, db = inicializar(dry_run)
    ok = 0
    for op in operaciones:
        if op["accion"] == "crear":
            ok += crear(auth_c, db, op, dry_run)
        elif op["accion"] == "cambiar_correo":
            ok += cambiar_correo(auth_c, db, op, dry_run)
        elif op["accion"] == "cambiar_datos":
            ok += cambiar_datos(auth_c, db, op, dry_run)
        elif op["accion"] == "cambiar_password":
            ok += cambiar_password(auth_c, db, op, dry_run)
        elif op["accion"] == "desactivar":
            ok += desactivar(auth_c, db, op, dry_run)
        else:
            print(f"\n  ✗ Acción desconocida: {op['accion']}")

    print("\n" + "=" * 60)
    print(f"  Operaciones exitosas: {ok}/{len(operaciones)}")
    print("=" * 60)
    if not dry_run and ok:
        print("\n  Recuerda enviar las contraseñas a los labs nuevos por correo.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Actualización puntual de labs CONCALAB en Firebase")
    p.add_argument("--dry-run", action="store_true", help="Simula sin escribir en Firebase")
    p.add_argument("--operaciones", default=OPERACIONES_PATH,
                   help=f"JSON con las operaciones (por defecto: {OPERACIONES_PATH})")
    args = p.parse_args()

    if not args.dry_run and not os.path.exists(CREDS_PATH):
        print(f"\n  ERROR: no se encontró la clave de servicio: {CREDS_PATH}\n")
        sys.exit(1)

    main(dry_run=args.dry_run, ruta_ops=args.operaciones)
