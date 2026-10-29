import sys
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from app.models.producto import ProductoTienda

app = create_app()
with app.app_context():
    # Buscamos todo lo que la Tienda 1 quiere enviar a la Central y lo marcamos como 'sincronizado'
    pendientes = ProductoTienda.query.filter_by(tienda_id=1, sync_estado='pendiente').all()
    print(f'Productos que T1 intentaba subir: {len(pendientes)}')
    for p in pendientes:
        p.sync_estado = 'sincronizado' # Le decimos que ya no envíe nada, que la Central tiene la verdad
    
    db.session.commit()
    print('¡EXITO! La Tienda 1 dejara de enviar datos erroneos a la Central.')
