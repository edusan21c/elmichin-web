from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from app.extensions import db

app = create_app()
app.app_context().push()

inactivos = Producto.query.filter_by(categoria='INACTIVO').all()
borrados = 0
protegidos = 0

print("Iniciando limpieza de basura (Sin ventas, sin stock, sin foto)...")

for p in inactivos:
    # Verificaciones estrictas por si acaso
    tiene_ventas = DetalleFactura.query.filter_by(producto_id=p.id).first() is not None
    
    pt_t1 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
    pt_t2 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=2).first()
    stock1 = pt_t1.cantidad if pt_t1 else 0
    stock2 = pt_t2.cantidad if pt_t2 else 0
    tiene_stock = (stock1 > 0) or (stock2 > 0)
    
    tiene_foto = bool(p.imagen and p.imagen.strip() and p.imagen != 'error.png')

    # Si no tiene nada, se borra
    if not (tiene_ventas or tiene_stock or tiene_foto):
        print(f"  Borrando: {p.nombre} (ID: {p.id})")
        # Borrar de las tiendas primero
        ProductoTienda.query.filter_by(producto_id=p.id).delete()
        # Borrar producto global
        db.session.delete(p)
        borrados += 1
    else:
        protegidos += 1

db.session.commit()
print("=====================================")
print(f"Limpieza terminada.")
print(f"Productos basura borrados: {borrados}")
print(f"Productos protegidos conservados: {protegidos}")
