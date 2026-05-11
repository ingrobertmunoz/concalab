"""
Importa laboratorios CONCALAB a Firebase desde el Excel:
  support/laboratorios_concalab.xlsx

Por cada laboratorio:
  1. Crea un usuario en Firebase Authentication (email + password)
  2. Crea un documento en Firestore → colección "laboratorios"

Requisitos:
  conda activate concalab
  pip install firebase-admin openpyxl

Credenciales:
  Descargar la clave de servicio desde Firebase Console:
    Configuración del proyecto → Cuentas de servicio → Generar nueva clave privada
  Guardar como: support/firebase-service-account.json  (NO subir a GitHub)

Uso:
  python scripts/importar_labs_firebase.py
  python scripts/importar_labs_firebase.py --dry-run   # solo simula, no escribe
"""

import sys
import argparse
import openpyxl
import firebase_admin
from firebase_admin import credentials, auth, firestore

# ── Configuración ─────────────────────────────────────────────────────────────

EXCEL_PATH   = "support/laboratorios_concalab.xlsx"
CREDS_PATH   = "support/concalab-uasd-64ff4-firebase-adminsdk-fbsvc-c400cdf10b.json"
HOJA         = "Laboratorios"

# Columnas del Excel (índice base 1)
COL_COD_INTERNO = 1
COL_COD_ANONIMO = 2
COL_NOMBRE      = 3
COL_REPR        = 4
COL_TELEFONO    = 5
COL_CORREO      = 6
COL_PASSWORD    = 7
COL_ACTIVO      = 8

# ── Helpers ───────────────────────────────────────────────────────────────────

def celda(fila, col):
    val = fila[col - 1].value
    return str(val).strip() if val is not None else ""

def inicializar_firebase(dry_run):
    if dry_run:
        print("  [DRY-RUN] Firebase no inicializado — solo simulación.\n")
        return None, None
    cred = credentials.Certificate(CREDS_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    return auth, db

# ── Importación ───────────────────────────────────────────────────────────────

def importar(dry_run=False):
    print("=" * 60)
    print("  CONCALAB — Importación de laboratorios a Firebase")
    print("=" * 60)

    auth_client, db = inicializar_firebase(dry_run)

    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb[HOJA]

    filas = list(ws.iter_rows(min_row=2))  # saltar encabezado
    total   = len(filas)
    ok      = 0
    errores = []
    omitidos = []

    for fila in filas:
        cod_interno = celda(fila, COL_COD_INTERNO)
        cod_anonimo = celda(fila, COL_COD_ANONIMO)
        nombre      = celda(fila, COL_NOMBRE)
        representante = celda(fila, COL_REPR)
        telefono    = celda(fila, COL_TELEFONO)
        correo      = celda(fila, COL_CORREO)
        password    = celda(fila, COL_PASSWORD)
        activo      = celda(fila, COL_ACTIVO).upper() == "SÍ"

        if not correo or "@" not in correo:
            omitidos.append(f"  Lab {cod_interno} ({nombre[:40]}) — sin correo válido")
            continue

        print(f"\n[{cod_interno:>3}] {nombre[:45]}")
        print(f"       Correo: {correo}")
        print(f"       Cód. anónimo: {cod_anonimo} | Password: {password}")

        if dry_run:
            print("       → [DRY-RUN] Se crearía en Auth + Firestore")
            ok += 1
            continue

        # 1. Crear usuario en Firebase Auth
        try:
            usuario = auth_client.create_user(
                email=correo.lower(),
                password=password,
                display_name=nombre,
                disabled=not activo,
            )
            uid = usuario.uid
            print(f"       ✓ Auth creado — uid: {uid}")
        except auth_client._auth_utils.EmailAlreadyExistsError:
            # Si ya existe, obtener el uid existente
            usuario = auth_client.get_user_by_email(correo.lower())
            uid = usuario.uid
            print(f"       ⚠ Auth ya existe — uid: {uid} (se actualiza Firestore)")
        except Exception as e:
            errores.append(f"  Lab {cod_interno} ({nombre[:35]}) — Auth: {e}")
            print(f"       ✗ Error Auth: {e}")
            continue

        # 2. Crear/actualizar documento en Firestore
        try:
            doc_data = {
                "uid":            uid,
                "cod_interno":    int(cod_interno) if cod_interno.isdigit() else cod_interno,
                "cod_anonimo":    cod_anonimo,
                "nombre":         nombre,
                "representante":  representante,
                "telefono":       telefono,
                "correo":         correo.lower(),
                "activo":         activo,
                "creado_en":      firestore.SERVER_TIMESTAMP,
            }
            db.collection("laboratorios").document(uid).set(doc_data)
            print(f"       ✓ Firestore — colección 'laboratorios' doc: {uid[:12]}...")
            ok += 1
        except Exception as e:
            errores.append(f"  Lab {cod_interno} ({nombre[:35]}) — Firestore: {e}")
            print(f"       ✗ Error Firestore: {e}")

    # ── Resumen ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  RESUMEN {'(DRY-RUN)' if dry_run else ''}")
    print(f"  Total filas procesadas : {total}")
    print(f"  Importados con éxito   : {ok}")
    print(f"  Con errores            : {len(errores)}")
    print(f"  Omitidos (sin correo)  : {len(omitidos)}")

    if omitidos:
        print("\n  Laboratorios omitidos (completar correo en el Excel):")
        for m in omitidos:
            print(m)

    if errores:
        print("\n  Errores:")
        for e in errores:
            print(e)

    print("=" * 60)

    if not dry_run and ok > 0:
        print(f"\n  ✓ {ok} laboratorios registrados en Firebase.")
        print("  Próximo paso: enviar contraseñas por correo a cada representante.")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importar laboratorios CONCALAB a Firebase")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin escribir en Firebase")
    args = parser.parse_args()

    if not args.dry_run:
        import os
        if not os.path.exists(CREDS_PATH):
            print(f"\n  ERROR: No se encontró el archivo de credenciales:")
            print(f"         {CREDS_PATH}")
            print(f"\n  Descárgalo desde Firebase Console:")
            print(f"    Configuración del proyecto → Cuentas de servicio")
            print(f"    → Generar nueva clave privada")
            print(f"    → Guardar como: {CREDS_PATH}")
            print(f"\n  Para probar sin escribir en Firebase:")
            print(f"    python scripts/importar_labs_firebase.py --dry-run\n")
            sys.exit(1)

    importar(dry_run=args.dry_run)
