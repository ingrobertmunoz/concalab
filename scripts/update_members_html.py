import json
import os
import re

LABS_JSON = '/media/ing-r/Windows/Users/ing_r/Proyectos PC/CONCALAB/data/laboratorios.json'
MIEMBROS_HTML = '/media/ing-r/Windows/Users/ing_r/Proyectos PC/CONCALAB/miembros.html'
INDEX_HTML = '/media/ing-r/Windows/Users/ing_r/Proyectos PC/CONCALAB/index.html'

def generate_card(lab):
    icon = "🏥" if lab['tipo'] == 'Público' else "🔬"
    if "sangre" in lab['nombre'].lower():
        icon = "🩸"
    
    return f"""
                <div class="member-card reveal" data-region="{lab['region']}">
                    <div class="member-logo">{icon}</div>
                    <h3 class="member-name">{lab['nombre']}</h3>
                    <p class="member-location">📍 {lab['direccion']}</p>
                    <span class="member-type">{lab['tipo']}</span>
                    <p class="member-since">Miembro desde {lab['año']}</p>
                </div>"""

def update_miembros_html(labs):
    with open(MIEMBROS_HTML, 'r', encoding='utf-8') as f:
        content = f.read()

    # Generate new grid content
    grid_content = "\n".join([generate_card(lab) for lab in labs])
    
    # Replace content between <div class="members-grid"> and </div>
    # Logic: Find start and end of the div content.
    start_marker = '<div class="members-grid">'
    end_marker = '</div>' # First closing div after start_marker? No, that might be risky if nested. 
    # But current structure is flat inside.
    # To be safe, let's look for the specific comment if it exists or just use split/replace
    
    # Actually, let's use a simpler marker approach or regex
    import re
    
    # Check if files have the container
    if start_marker not in content:
        print("Error: Could not find members-grid in miembros.html")
        return

    # Using split approach for safety instead of regex which might get confused by nested divs if I'm not careful.
    # But since I know the file structure (I viewed it), it ends with </div> and then <!-- CTA para unirse -->
    
    # Let's replace everything between members-grid and <!-- CTA --> to be safer about closing divs
    # Viewed file: 
    # <div class="members-grid">
    # ... cards ...
    # </div>
    # 
    # <!-- CTA para unirse -->
    
    pattern = r'(<div class="members-grid">)([\s\S]*?)(</div>\s*<!-- CTA para unirse -->)'
    
    if not re.search(pattern, content):
        # Fallback if comment is missing or spacing varies
        print("Pattern match failed, using simple innerhtml replacement")
        # Try to match the div and its closing tag. 
        # Since I wrote the file viewing logic, I can see lines 248-325.
        pass
        
    new_content = re.sub(
        r'(<div class="members-grid">)[\s\S]*?(<!-- CTA para unirse -->)', 
        f'\\1\n{grid_content}\n            </div>\n\n            \\2', 
        content
    )
    
    # Also update the stats count in miembros.html
    # <h3 class="counter" data-target="100">0</h3> -> 100 is Labs Activos
    # Regex for that specific counter might be tricky if not unique.
    # Line 214: <h3 class="counter" data-target="100">0</h3>
    # Line 215: <p>Laboratorios Activos</p>
    
    # Replace data-target for "Laboratorios Activos"
    new_content = re.sub(
        r'(<h3 class="counter" data-target=")\d+(">\d+</h3>\s*<p>Laboratorios Activos</p>)',
        f'\\g<1>{len(labs)}\\2',
        new_content
    )
    
    # Calculate unique locations (Estimating provinces/cities)
    regions = set([lab['region'] for lab in labs]) # Broad regions
    # But we want 'Provincias Representadas'. The JSON has region but we parsed addresses.
    # A simple proxy is counting unique keywords found in addresses or just mapping regions to count.
    # 32 was the placeholder. 
    # Let's count approximate unique locations based on region/address analysis or just set a more realistic number based on the 37 labs.
    # Detailed analysis from 37 labs: SD, Santiago, La Vega, Puerto Plata, Bonao, San Cristobal, Azua, Bani, Barahona, San Pedro, La Romana, Higuey, Samana, Ocoa.
    # That's about 14 provinces. 
    # Let's do a quick set count of keywords if they appear in address
    
    provinces_keywords = [
        'santo domingo', 'distrito nacional', 'santiago', 'la vega', 'puerto plata', 
        'bonao', 'monseñor nouel', 'duarte', 'san francisco', 'nagua', 'samaná', 'samana', 
        'san pedro', 'la romana', 'higüey', 'altagracia', 'hato mayor', 'seibo', 
        'san cristóbal', 'azua', 'san juan', 'barahona', 'peravia', 'baní', 'bani', 
        'ocoa', 'elias piña', 'pedernales', 'independencia', 'bahoruco', 'monte plata',
        'dajabón', 'monte cristi', 'santiago rodríguez', 'valverde', 'mao', 'espaillat', 'moca',
        'hermanas mirabal', 'salcedo', 'sánchez ramírez', 'cotuí'
    ]
    
    found_provinces = set()
    for lab in labs:
        addr = lab['direccion'].lower()
        for prov in provinces_keywords:
            if prov in addr:
                # Normalize names (e.g. bani -> peravia/bani)
                if prov in ['santo domingo', 'distrito nacional', 'd.n', 'herrera', 'villa mella', 'los mina', 'ozama', 'evaristo morales']:
                    found_provinces.add('Santo Domingo')
                elif prov in ['bonao', 'monseñor nouel', 'maimón']:
                    found_provinces.add('Monseñor Nouel')
                elif prov in ['baní', 'bani']:
                    found_provinces.add('Peravia')
                elif prov in ['higüey', 'altagracia']:
                    found_provinces.add('La Altagracia')
                elif prov in ['samaná', 'samana']:
                    found_provinces.add('Samaná')
                elif prov in ['san cristóbal']:
                    found_provinces.add('San Cristóbal')
                elif prov == 'la vega' or prov == 'jarabacoa':
                    found_provinces.add('La Vega')
                else:
                    found_provinces.add(prov.title())
    
    unique_provinces_count = len(found_provinces)
    # Default to at least 1 if 0 found (unlikely)
    if unique_provinces_count == 0: unique_provinces_count = 1
    
    # Update Provincias Representadas count
    # Regex: <h3 class="counter" data-target="32">0</h3>
    # Line 218: <h3 class="counter" data-target="32">0</h3>
    # Line 219: <p>Provincias Representadas</p>
    
    new_content = re.sub(
        r'(<h3 class="counter" data-target=")\d+(">\d+</h3>\s*<p>Provincias Representadas</p>)',
        f'\\g<1>{unique_provinces_count}\\2',
        new_content
    )
    
    with open(MIEMBROS_HTML, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Updated miembros.html with {len(labs)} labs and {unique_provinces_count} provinces.")


def update_index_html(labs):
    with open(INDEX_HTML, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Update counter for Laboratorios Participantes
    # Line 239: <h3 class="counter" data-target="100"
    # Line 240: style="...">0</h3>
    # Line 241: <p class="card-text" style="font-weight: 600;">Laboratorios Participantes</p>
    
    # This regex needs to be careful about newlines
    new_content = re.sub(
        r'(data-target=")\d+("\s*style="[^"]*">0</h3>\s*<p[^>]*>Laboratorios Participantes</p>)',
        f'\\g<1>{len(labs)}\\2',
        content,
        flags=re.DOTALL
    )
    
    with open(INDEX_HTML, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Updated index.html counter to {len(labs)}.")

def main():
    with open(LABS_JSON, 'r', encoding='utf-8') as f:
        labs = json.load(f)
    
    update_miembros_html(labs)
    update_index_html(labs)

if __name__ == "__main__":
    main()
