import json
import random

LABS_FILE = 'data/laboratorios.json'
SECRET_FILE = 'support/codigos_laboratorios_secretos.md'
CHARTS_DATA_FILE = 'data/ensayos_aptitud.json'

def anonymize():
    # 1. Read Labs
    with open(LABS_FILE, 'r', encoding='utf-8') as f:
        labs = json.load(f)
    
    # 2. Assign Codes
    # We will shuffle them slightly so the order doesn't match alphabetical order 1:1, protecting identity further?
    # Or just sequential is fine. Let's do sequential for simplicity but ensure mapping is saved.
    
    mapping = []
    mapped_labs = []
    
    for idx, lab in enumerate(labs):
        code = f"LAB-{idx+1:03d}"
        lab['codigo'] = code
        mapping.append(f"| {code} | {lab['nombre']} | {lab['region']} |")
        mapped_labs.append(lab)
        
    # 3. Save Secret Mapping Markdown
    with open(SECRET_FILE, 'w', encoding='utf-8') as f:
        f.write("# Códigos Secretos de Laboratorios\n\n")
        f.write("| Código | Nombre Real | Región |\n")
        f.write("|--------|-------------|--------|\n")
        f.write("\n".join(mapping))
    
    print(f"Generado archivo secreto: {SECRET_FILE}")
    
    # 4. Regenerate Charts Data with Codes
    # We will recreate the simulated data structure but using codes
    
    # helper to find code by name (simulating previous logic)
    # The previous charts.js logic used random z-scores. We can just generate new random data for the codes.
    
    analytes_data = {
        "metadata": {
            "ronda": "2024-01",
            "fecha": "Enero 2024",
            "total_laboratorios": len(labs)
        },
        "resultados": []
    }
    
    # Generate data for Glucosa and Colesterol
    analitos_simulados = [
        {"nombre": "Glucosa", "unidades": "mg/dL"},
        {"nombre": "Colesterol Total", "unidades": "mg/dL"}
    ]
    
    for analito in analitos_simulados:
        resultados_analito = {
            "analito": analito["nombre"],
            "unidades": analito["unidades"],
            "datos": []
        }
        
        for lab in mapped_labs:
            # Simulate generic Z-score
            z_score = round(random.uniform(-3.5, 3.5), 2)
            # Make most "Satisfactory"
            if random.random() > 0.2:
                z_score = round(random.uniform(-1.9, 1.9), 2)
                
            resultados_analito["datos"].append({
                "laboratorio": lab["codigo"], # USING CODE HERE
                "z_score": z_score,
                "resultado": round(random.uniform(70, 110), 1) # Mock value
            })
        
        analytes_data["resultados"].append(resultados_analito)
        
    with open(CHARTS_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(analytes_data, f, ensure_ascii=False, indent=2)
        
    print(f"Regenerado datos anónimos: {CHARTS_DATA_FILE}")

if __name__ == "__main__":
    anonymize()
