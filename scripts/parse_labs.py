import re
import json

def parse_labs(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Normalize newlines
    content = content.replace('\r\n', '\n')
    
    # Split by bullets or double newlines to find chunks? 
    # The format seems to vary. Let's try splitting by '•' 
    chunks = content.split('•')
    
    labs = []
    
    for chunk in chunks[1:]: # Skip first empty chunk before first bullet
        lines = chunk.strip().split('\n')
        name = lines[0].strip()
        
        address = "Desconocida"
        year = "Desconocido"
        
        # Searching for patterns
        address_match = re.search(r'(?:Dirección|DIRECCION):\s*(.*)', chunk, re.IGNORECASE)
        if address_match:
            address = address_match.group(1).strip()
            
        year_match = re.search(r'(?:AÑO|Año):\s*(\d{4})', chunk, re.IGNORECASE)
        if year_match:
            year = year_match.group(1).strip()
            
        # Infer region based on address (Simple keyword matching)
        region = 'otro'
        address_lower = address.lower()
        
        dn_keywords = ['santo domingo', 'distrito nacional', 'd.n', 'herrera', 'villa mella', 'evaristo morales', 'san jerónimo', 'san jeronimo', 'gazcue', 'don bosco', 'alma máter', 'alma mater', 'piantini', 'naco', 'polígono central', 'la fe', 'capotillo', 'honduras', 'trabajadores', 'mata hambre', 'la feria', 'pedro ignacio espaillat']
        norte_keywords = ['santiago', 'la vega', 'puerto plata', 'bonao', 'monseñor nouel', 'jarabacoa', 'maimón', 'cibao', 'san francisco', 'nagua', 'samaná', 'samana', 'cotuí', 'moca', 'matilde viñas']
        este_keywords = ['san pedro', 'la romana', 'higüey', 'higuey', 'este', 'bávaro', 'punta cana', 'hato mayor', 'seibo', 'ozama', 'zona oriental', 'los mina', 'alma rosa']
        sur_keywords = ['san cristóbal', 'san cristobal', 'azua', 'san juan', 'barahona', 'baní', 'bani', 'ocoa', 'sur', 'elias piña', 'pedernales', 'independencia', 'bahoruco', 'peravia']

        if any(x in address_lower for x in dn_keywords):
            region = 'distrito-nacional'
        elif any(x in address_lower for x in norte_keywords):
            region = 'norte' 
            if 'santiago' in address_lower:
                region = 'santiago'
        elif any(x in address_lower for x in este_keywords):
            region = 'este'
        elif any(x in address_lower for x in sur_keywords):
            region = 'sur'
            
        labs.append({
            "nombre": name,
            "direccion": address,
            "año": year,
            "region": region,
            "tipo": "Privado" if "hospital" not in name.lower() and "maternidad" not in name.lower() and "centro de sangre" not in name.lower() else "Público" # Heuristic
        })
        
    return labs

labs = parse_labs('/media/ing-r/Windows/Users/ing_r/Proyectos PC/CONCALAB/support/Labs info.md')

# Output to JSON
import os
os.makedirs('/media/ing-r/Windows/Users/ing_r/Proyectos PC/CONCALAB/data', exist_ok=True)
with open('/media/ing-r/Windows/Users/ing_r/Proyectos PC/CONCALAB/data/laboratorios.json', 'w', encoding='utf-8') as f:
    json.dump(labs, f, indent=2, ensure_ascii=False)

print(f"Parsed {len(labs)} laboratories.")
for lab in labs:
    print(f"- {lab['nombre']} ({lab['region']})")
