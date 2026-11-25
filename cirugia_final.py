from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- CIRUGÍA FINAL EN LA CENTRAL ---")
barcode_unicornio = '7702993056745'

# 1. Buscamos al Unicornio
p_unicornio = Producto.query.filter(Producto.nombre.ilike('%Trululu Unicornio%')).first()

if p_unicornio:
    print(f"Unicornio encontrado (ID: {p_unicornio.id})")
    
    # 2. Buscamos quién tiene el código conflictivo AHORA MISMO
    p_conflicto = Producto.query.filter(Producto.codigo_barras == barcode_unicornio, Producto.id != p_unicornio.id).first()
    
    if p_conflicto:
        print(f"  ¡Conflicto detectado! El producto ID {p_conflicto.id} ({p_conflicto.nombre}) ya tiene ese código.")
        # Lo aislamos y GUARDAMOS PRIMERO
        p_conflicto.codigo_barras = f'BORRAR-CONFLICTO-{p_conflicto.id}'
        p_conflicto.categoria = 'INACTIVO'
        db.session.commit()
        print("  Conflicto aislado y guardado en la base de datos.")
    else:
        print("  No hay conflictos de código en este momento.")

    # 3. Ahora sí, le ponemos el código real al Unicornio
    p_unicornio.codigo_barras = barcode_unicornio
    p_unicornio.nombre = 'B. Trululu Unicornio 100g 43g'
    p_unicornio.categoria = 'dulces'
    
    # 4. Lo preparamos para sincronizar
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_unicornio.id, tienda_id=t_id).first()
        if pt:
            pt.sync_estado = 'pendiente'
            
    db.session.commit()
    print("  ¡Unicornio corregido y listo para enviar!")
else:
    print("  No se encontró el Unicornio.")

# 5. Arreglamos el Shampoo H&S
p_hs = Producto.query.filter(Producto.nombre.ilike('%H&S%Rosado%')).first()
if p_hs:
    p_hs.nombre = 'Un. H&S (Hys) Shampoox12 Rosado'
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_hs.id, tienda_id=t_id).first()
        if pt:
            pt.sync_estado = 'pendiente'
    db.session.commit()
    print("  Shampoo H&S estandarizado.")

# 6. Marcamos el L&M para enviar a las tiendas
p_lm = Producto.query.filter(Producto.nombre.ilike('%L&M Verde & Rojo 20u%')).first()
if p_lm:
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_lm.id, tienda_id=t_id).first()
        if pt:
            pt.sync_estado = 'pendiente'
    db.session.commit()
    print("  L&M marcado para sincronizar.")

print("¡Cirugía completada con éxito!")
