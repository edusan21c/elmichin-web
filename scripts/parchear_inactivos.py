import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_TO_PATCH = [
    'app/blueprints/inventario/routes.py',
    'app/blueprints/facturacion/routes.py',
    'app/blueprints/venta_rapida/routes.py'
]

def patch_file(rel_path):
    full_path = os.path.join(BASE_DIR, rel_path)
    if not os.path.exists(full_path):
        print(f"Archivo no encontrado: {rel_path}")
        return

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "Producto.categoria != 'INACTIVO'" in content:
        print(f"✅ Ya estaba parcheado: {rel_path}")
        return

    # Reemplazar todas las consultas comunes
    content = content.replace("Producto.query.filter(", "Producto.query.filter(Producto.categoria != 'INACTIVO').filter(")
    content = content.replace("Producto.query.all()", "Producto.query.filter(Producto.categoria != 'INACTIVO').all()")
    content = content.replace("Producto.query.order_by(", "Producto.query.filter(Producto.categoria != 'INACTIVO').order_by(")
    content = content.replace("Producto.query.paginate(", "Producto.query.filter(Producto.categoria != 'INACTIVO').paginate(")
    content = content.replace("Producto.query.join(", "Producto.query.filter(Producto.categoria != 'INACTIVO').join(")

    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Parcheado exitosamente: {rel_path}")

print("--- APLICANDO FILTRO DE INACTIVOS ---")
for f in FILES_TO_PATCH:
    patch_file(f)
print("\n--- TERMINADO ---")
print("Reinicia el servicio con: Restart-Service -Name 'MichinFlask'")