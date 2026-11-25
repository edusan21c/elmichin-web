from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# Consultamos el producto 2923 en la Central
p = Producto.query.get(2923)
if p:
    print(f"Producto en Central: {p.nombre}")
    pt = ProductoTienda.query.filter_by(producto_id=2923, tienda_id=2).first()
    if pt:
        print(f"Estado de sincronización para Tienda 2 en la Central: {pt.sync_estado}")
    else:
        print("El producto no tiene registro de stock para Tienda 2 en la Central.")
else:
    print("El producto NO EXISTE en la Central.")
