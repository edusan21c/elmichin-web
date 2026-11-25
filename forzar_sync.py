from app import create_app
from app.models.producto import ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# Vamos a buscar el producto 2923 y ponerlo como 'pendiente' en Tienda 1 y 2
registros = ProductoTienda.query.filter_by(producto_id=2923).all()
if registros:
    for r in registros:
        r.sync_estado = 'pendiente'
    db.session.commit()
    print("¡Listo! El producto 2923 se ha puesto en estado 'pendiente'.")
    print("La Central lo enviará en el próximo ciclo de sincronización (en menos de 1 minuto).")
else:
    print("No se encontraron registros de este producto en Tienda 1 o 2.")
