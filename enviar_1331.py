from app import create_app
from app.models.producto import ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# Buscamos el producto 1331 (Club Social Integral) y lo marcamos como pendiente para T2
pt = ProductoTienda.query.filter_by(producto_id=1331, tienda_id=2).first()
if pt:
    pt.sync_estado = 'pendiente'
    db.session.commit()
    print("Producto 1331 marcado como PENDIENTE en la Central.")
else:
    print("No se encontró el registro del producto 1331 para Tienda 2.")

# Borramos el castigo de la central
import os
if os.path.exists('C:\\michin_web\\.sync_backoff.json'):
    os.remove('C:\\michin_web\\.sync_backoff.json')
    print("Castigo de la Central eliminado.")
