import sys
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from app.models.producto import ProductoTienda

app = create_app()
with app.app_context():
    # Esto marca TODOS los productos para que se envien a las tiendas
    print('Forzando actualizacion de todos los productos en la Central...')
    cantidad = ProductoTienda.query.filter(ProductoTienda.sync_estado != 'pendiente').update({'sync_estado': 'pendiente'}, synchronize_session=False)
    db.session.commit()
    print(f'¡EXITO! Se marcaron {cantidad} productos para actualizarse en las tiendas.')
