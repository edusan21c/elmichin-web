from app import create_app
from app.models.producto import Producto
from app.extensions import db

app = create_app()
app.app_context().push()

# Revisamos qué pasó con las Tajaditas (ID 2923)
p = Producto.query.get(2923)
if p:
    print(f"El producto 2923 existe. Nombre: {p.nombre} | Categoría: {p.categoria}")
else:
    print("El producto 2923 (Tajaditas) ya no existe o fue borrado.")
