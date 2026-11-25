from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db
import os

app = create_app()
app.app_context().push()

productos = Producto.query.filter(Producto.nombre.ilike('%Club Social%')).all()
ids = [p.id for p in productos]
ProductoTienda.query.filter(ProductoTienda.producto_id.in_(ids)).update({'sync_estado': 'pendiente'}, synchronize_session=False)
db.session.commit()

if os.path.exists('C:\\michin_web\\.sync_backoff.json'):
    os.remove('C:\\michin_web\\.sync_backoff.json')

print("Listo. Club Social marcadas como pendientes.")
