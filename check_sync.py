from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

app = create_app()
app.app_context().push()

print("==================================================")
print("   ESTADO DE SINCRONIZACION (SOLO LECTURA)        ")
print("==================================================")

pendientes_t1 = ProductoTienda.query.filter_by(tienda_id=1, sync_estado='pendiente').count()
pendientes_t2 = ProductoTienda.query.filter_by(tienda_id=2, sync_estado='pendiente').count()

print(f"Registros pendientes por enviar de Tienda 1: {pendientes_t1}")
print(f"Registros pendientes por enviar de Tienda 2: {pendientes_t2}")

# Buscamos si el producto que creaste está pendiente
nuevo_prod = Producto.query.order_by(Producto.id.desc()).first()
if nuevo_prod:
    print(f"\nUltimo producto creado: {nuevo_prod.nombre} (ID: {nuevo_prod.id})")
    for t in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=nuevo_prod.id, tienda_id=t).first()
        if pt:
            print(f"  - En Tienda {t}, estado de sync: {pt.sync_estado}")
        else:
            print(f"  - En Tienda {t}, NO EXISTE registro de stock.")
