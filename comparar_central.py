from app import create_app
from app.models.producto import Producto
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- BASE DE DATOS DE LA CENTRAL (PRODUCTOS TRULULU) ---")
palabras = ['Trululu', 'Caramelo', 'Fresa', 'Banana', 'Volcan', 'Unicornio']

for palabra in palabras:
    prods = Producto.query.filter(Producto.nombre.ilike(f'%{palabra}%')).all()
    for p in prods:
        print(f"ID: {p.id} | Nombre: '{p.nombre}' | Cod: {p.codigo_barras} | Cat: {p.categoria}")
print("--------------------------------------------------------")
