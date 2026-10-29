from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

app = create_app()
with app.app_context():
    # 1. Arreglamos el precio del producto real (buscando por su nombre exacto)
    p_real = Producto.query.filter_by(nombre='Un. Mechas Locas Sabores Frutales').first()
    if p_real:
        pres = ProductoTienda.query.filter_by(producto_id=p_real.id, tienda_id=1).first()
        if pres:
            pres.precio_venta = 3700
            pres.cantidad = 988
            pres.sync_estado = 'pendiente'
        print(f'Producto real arreglado: {p_real.nombre} (ID: {p_real.id})')
    
    # 2. Ocultamos la copia para que no estorbe nunca más
    p_copia = Producto.query.get(1616)
    if p_copia:
        p_copia.categoria = 'INACTIVO'
        p_copia.nombre = 'Un. Mechas Locas Sabores Frutales (Oculto)'
        print(f'Copia ocultada correctamente. (ID: {p_copia.id})')

    db.session.commit()
    print('¡PROCESO TERMINADO CON EXITO!')
