from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- CORRECCIÓN MAESTRA FINAL ---")

# 1. ARREGLAR EL SHAMPOO H&S (Reactivamos el 2943 que tenía el código real)
p_hs = Producto.query.get(2943)
if p_hs:
    p_hs.nombre = 'R. H&S (HYS) Shampoox12 Rosado (head&Shoulders)'
    p_hs.categoria = 'aseo'
    for t in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_hs.id, tienda_id=t).first()
        if pt:
            pt.precio_venta = 5000  # Ponle un precio real, ajusta si es otro
            pt.sync_estado = 'pendiente'
    print("  H&S Rosado (ID 2943) reactivado con su nombre original.")

# 2. ARREGLAR EL L&M (Tenía precio 0)
p_lm = Producto.query.get(1373)
if p_lm:
    for t in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_lm.id, tienda_id=t).first()
        if pt:
            pt.precio_venta = 5000  # Ponle el precio real, ajusta si es otro
            pt.sync_estado = 'pendiente'
    print("  L&M (ID 1373) actualizado con precio.")

# 3. ASEGURAR EL UNICORNIO REAL (2296)
p_uni = Producto.query.get(2296)
if p_uni:
    for t in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_uni.id, tienda_id=t).first()
        if pt:
            pt.sync_estado = 'pendiente'
    print("  Unicornio real (ID 2296) listo para sincronizar.")

# 4. MARCAR T1 Y T2 PARA QUE EL WORKER ENVÍE TODO
# Nota: La Central envía a T1 y T2, no necesita un tienda_id=0.
ProductoTienda.query.filter(ProductoTienda.tienda_id.in_([1, 2])).update({'sync_estado': 'pendiente'})

db.session.commit()
print("¡Listo! Todo marcado. Corre el Worker para enviar a la nube.")
