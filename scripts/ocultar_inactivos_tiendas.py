import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_TO_PATCH = [
    'app/blueprints/inventario/routes.py',
    'app/blueprints/facturacion/routes.py',
    'app/blueprints/venta_rapida/routes.py'
]

def patch_file(rel_path):
    full_path = os.path.join(BASE_DIR, rel_path)
    if not os.path.exists(full_path):
        print(f"Archivo no encontrado (saltando): {rel_path}")
        return

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "Producto.categoria != 'INACTIVO'" in content:
        print(f"✅ Ya estaba oculto en: {rel_path}")
        return

    # Regex para inyectar el filtro de inactivos en las consultas
    content = re.sub(r'Producto\.query\.filter\(', r"Producto.query.filter(Producto.categoria != 'INACTIVO').filter(", content)
    content = re.sub(r'Producto\.query\.all\(\)', r"Producto.query.filter(Producto.categoria != 'INACTIVO').all()", content)
    content = re.sub(r'Producto\.query\.order_by\(', r"Producto.query.filter(Producto.categoria != 'INACTIVO').order_by(", content)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Parcheado y oculto en: {rel_path}")

for f in FILES_TO_PATCH:
    patch_file(f)

print("\n--- TERMINADO ---")
print("Los productos INACTIVOS ya no deberían salir en el sistema normal.")