"""
Actualización puntual de laboratorios en Firebase (Auth + Firestore).

A diferencia de `importar_labs_firebase.py` (que recorre TODO el Excel y usa
.set() sobre cada doc), este script solo toca los laboratorios definidos en
OPERACIONES, sin alterar el resto. Maneja dos casos:

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

Uso:
  python scripts/actualizar_labs_firebase.py --dry-run   # simula, no escribe
  python scripts/actualizar_labs_firebase.py             # escribe en Firebase
"""

import sys
import os
import argparse
import firebase_admin
from firebase_admin import credentials, auth, firestore

CREDS_PATH = "support/concalab-uasd-64ff4-firebase-adminsdk-fbsvc-c400cdf10b.json"

# ── Operaciones a ejecutar ────────────────────────────────────────────────────
# Editar esta lista para cada ronda de cambios.

OPERACIONES = [
    # ── Ejemplos de cada acción (descomenta y edita lo que necesites) ──────────

    # {
    #     "accion": "crear",
    #     "cod_interno": 147,
    #     "cod_anonimo": "XX9",          # 2 letras + 1 dígito, ÚNICO (no repetir)
    #     "nombre": "Laboratorio Clínico Ejemplo",
    #     "representante": "Nombre del contacto",
    #     "telefono": "809-000-0000",
    #     "correo": "ejemplo@correo.com",
    #     "password": "ABCD1234",        # mín. 6 caracteres; enviar al lab por correo
    #     "activo": True,
    # },

    # {
    #     "accion": "cambiar_correo",
    #     "cod_interno": 144,
    #     "correo_nuevo": "nuevo@correo.com",
    # },

    # {
    #     "accion": "cambiar_datos",     # solo incluye los campos a cambiar
    #     "cod_interno": 144,
    #     "campos": {
    #         "nombre": "Nombre corregido",
    #         "representante": "Nuevo representante",
    #         "telefono": "809-111-2222",
    #     },
    # },

    # {
    #     "accion": "cambiar_password",
    #     "cod_interno": 144,
    #     "password_nuevo": "NUEVA1234",  # enviar al lab por correo
    # },

    # {
    #     "accion": "desactivar",
    #     "cod_interno": 144,
    #     "activo": False,                # False = bloquea login; True = reactiva
    # },
]


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


def main(dry_run):
    print("=" * 60)
    print(f"  CONCALAB — Actualización puntual de labs {'(DRY-RUN)' if dry_run else ''}")
    print("=" * 60)

    auth_c, db = inicializar(dry_run)
    ok = 0
    for op in OPERACIONES:
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
    print(f"  Operaciones exitosas: {ok}/{len(OPERACIONES)}")
    print("=" * 60)
    if not dry_run and ok:
        print("\n  Recuerda enviar las contraseñas a los labs nuevos por correo.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Actualización puntual de labs CONCALAB en Firebase")
    p.add_argument("--dry-run", action="store_true", help="Simula sin escribir en Firebase")
    args = p.parse_args()

    if not args.dry_run and not os.path.exists(CREDS_PATH):
        print(f"\n  ERROR: no se encontró la clave de servicio: {CREDS_PATH}\n")
        sys.exit(1)

    main(dry_run=args.dry_run)
