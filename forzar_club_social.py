from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db
import os

app = create_app()
app.app_context().push()

# 1. Buscamos los productos de Club Social
productos = Producto.query.filter(Producto.nombre.ilike('%Club Social%')).all()
ids = [p.id for p in productos]
print(f"Productos encontrados: {[p.nombre for p in productos]}")

# 2. Los marcamos como pendientes en Tienda 1 y Tienda 2
cantidad = ProductoTienda.query.filter(ProductoTienda.producto_id.in_(ids)).update({'sync_estado': 'pendiente'}, synchronize_session=False)
db.session.commit()
print(f"Se marcaron {cantidad} registros de Club Social como pendientes.")

# 3. Borramos el castigo
if os.path.exists('C:\\michin_web\\.sync_backoff.json'):
    os.remove('C:\\michin_web\\.sync_backoff.json')
    print("Castigo eliminado.")
