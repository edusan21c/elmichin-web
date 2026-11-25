from app import create_app
from app.models.producto import Producto
from app.extensions import db

app = create_app()
app.app_context().push()

# 1. Ver los últimos 100 productos creados (los más recientes)
ultimos = Producto.query.order_by(Producto.id.desc()).limit(100).all()
print("--- ULTIMOS 15 PRODUCTOS CREADOS EN LA CENTRAL ---")
for p in ultimos[:15]:
    print(f"ID: {p.id} | Nombre: {p.nombre} | Cat: {p.categoria}")

# 2. Buscar productos que tengan el texto "Auto-Fix" (esto pasa cuando hay duplicados)
autofix = Producto.query.filter(Producto.nombre.ilike('%Auto-Fix%')).all()
print(f"\n--- PRODUCTOS CON NOMBRE 'Auto-Fix': {len(autofix)} ---")
for p in autofix[:10]:
    print(f"ID: {p.id} | Nombre: {p.nombre}")

# 3. Contar cuántos productos están INACTIVOS vs ACTIVOS
total = Producto.query.count()
inactivos = Producto.query.filter_by(categoria='INACTIVO').count()
print(f"\nTotal en base de datos: {total}")
print(f"Total INACTIVOS: {inactivos}")
print(f"Total ACTIVOS: {total - inactivos}")
