from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- ARREGLO FINAL DEL L&M Y LIMPIEZA DEL SHAMPOO DUPLICADO ---")

# 1. Marcamos el L&M para enviar a las tiendas
p_lm = Producto.query.filter(Producto.nombre.ilike('%L&M Verde & Rojo 20u%')).first()
if p_lm:
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_lm.id, tienda_id=t_id).first()
        if pt:
            pt.sync_estado = 'pendiente'
    print("  L&M marcado para enviar a las tiendas.")
    db.session.commit()
else:
    print("  No se encontró el L&M.")

# 2. Inactivamos el shampoo duplicado (ID 2943) para que no estorbe
p_shampoo_duplicado = Producto.query.filter_by(id=2943).first()
if p_shampoo_duplicado:
    p_shampoo_duplicado.categoria = 'INACTIVO'
    p_shampoo_duplicado.nombre = 'Un. H&S (Hys) Shampoox12 Rosado (DUPLICADO)'
    print("  Shampoo duplicado (ID 2943) inactivado y renombrado.")
    db.session.commit()

print("¡Listo! Todo arreglado. Ahora corre el Worker para enviar a la nube.")
