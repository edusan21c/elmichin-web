from app import create_app
from app.models.producto import ProductoTienda
from app.extensions import db
import os

app = create_app()
app.app_context().push()

# 1. Marcamos TODO como pendiente para que viaje a la nube
cantidad = ProductoTienda.query.update({'sync_estado': 'pendiente'})
db.session.commit()
print(f"¡Listo! Se marcaron {cantidad} productos como pendientes.")

# 2. Borramos el castigo de la Central
if os.path.exists('C:\\michin_web\\.sync_backoff.json'):
    os.remove('C:\\michin_web\\.sync_backoff.json')
    print("Castigo eliminado.")
