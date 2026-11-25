from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- VERIFICANDO LOS PRODUCTOS EN LA CENTRAL ---")
nombres = [
    'B. Trululu Caramelo Salado 100g 54g',
    'B. Trululu Helado Fresa 100g 54g',
    'B. Trululu Masmelos Choco Banana 100g 50g',
    'B. Trululu Volcan Chocolate 100g 54g'
]

for n in nombres:
    # Buscamos por el nombre exacto
    p = Producto.query.filter(Producto.nombre == n).first()
    if p:
        pt = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
        stock = pt.cantidad if pt else 0
        print(f"  ID: {p.id} | Nombre: '{p.nombre}' | Cat: {p.categoria} | Stock T1: {stock}")
    else:
        print(f"  NO ENCONTRADO: {n}")
