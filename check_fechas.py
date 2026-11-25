from app import create_app
from app.models.producto import Producto
from app.extensions import db
from sqlalchemy import text

app = create_app()
app.app_context().push()

# Vamos a mirar las columnas de la tabla productos
columnas = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='producto'")).fetchall()
print("Columnas de la tabla Producto:")
for c in columnas:
    print(f" - {c[0]}")

# Consultamos el producto 2923 en la central
p = Producto.query.get(2923)
if p:
    print("\nDatos del producto 2923 en Central:")
    print(f"Nombre: {p.nombre}")
    if hasattr(p, 'updated_at'): print(f"Updated_at: {p.updated_at}")
    if hasattr(p, 'created_at'): print(f"Created_at: {p.created_at}")
