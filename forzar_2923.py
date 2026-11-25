from app import create_app
from app.models.producto import ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# Ponemos el producto 2923 como pendiente para Tienda 2
pt = ProductoTienda.query.filter_by(producto_id=2923, tienda_id=2).first()
if pt:
    pt.sync_estado = 'pendiente'
    db.session.commit()
    print("Producto 2923 marcado como pendiente en la Central.")
else:
    print("No se encontró el producto 2923.")
