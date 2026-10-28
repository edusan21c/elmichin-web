import re
import os

base = r'C:\michin_web'

# 1. Arreglar el Inventario Normal (forms.py)
forms_path = os.path.join(base, 'app', 'blueprints', 'inventario', 'forms.py')
with open(forms_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_choices = """choices=[
            ('', '-- Sin categoría --'),
            ('dulce', 'Dulce'),
            ('cigarro', 'Cigarrillo'),
            ('bebida', 'Bebida'),
            ('snack', 'Snack / Mecato'),
            ('aseo', 'Aseo'),
            ('licor', 'Licor'),
            ('otro', 'Otro'),
            ('abarrotes', 'Abarrotes'),
            ('panaderia', 'Panadería'),
            ('desechables', 'Desechables'),
            ('INACTIVO', 'INACTIVO (Ocultar)'),
        ],"""
content = re.sub(r"choices=\[\s*\('', '-- Sin categor.*?\),\s*\]", new_choices, content, flags=re.DOTALL)
with open(forms_path, 'w', encoding='utf-8') as f:
    f.write(content)

# 2. Arreglar el Inventario Pro (index.html)
html_path = os.path.join(base, 'app', 'templates', 'inventario_pro', 'index.html')
with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

new_options = """<select class="form-select" id="edit-categoria" name="categoria">
        <option value="">-- Sin categoría --</option>
        <option value="dulce">Dulce</option>
        <option value="cigarro">Cigarrillo</option>
        <option value="bebida">Bebida</option>
        <option value="snack">Snack / Mecato</option>
        <option value="aseo">Aseo</option>
        <option value="licor">Licor</option>
        <option value="otro">Otro</option>
        <option value="abarrotes">Abarrotes</option>
        <option value="panaderia">Panadería</option>
        <option value="desechables">Desechables</option>
        <option value="INACTIVO">INACTIVO (Ocultar)</option>
    </select>"""
html_content = re.sub(r'<select[^>]*id="edit-categoria"[^>]*>.*?</select>', new_options, html_content, flags=re.DOTALL)
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("✅ Categorías unificadas con éxito en Normal y Pro.")