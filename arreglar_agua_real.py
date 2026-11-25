from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- BUSCANDO EL VERDADERO AGUA CIELO EN LA CENTRAL ---")

# 1. Buscamos quién tiene el código real
p_real = Producto.query.filter_by(codigo_barras='77072445612').first()
if p_real:
    print(f"  ENCONTRADO: ID: {p_real.id} | Nombre: '{p_real.nombre}' | Cat: {p_real.categoria}")
    
    # Lo activamos y le damos stock/precio por si acaso
    p_real.categoria = 'bebida'
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_real.id, tienda_id=t_id).first()
        if not pt:
            pt = ProductoTienda(producto_id=p_real.id, tienda_id=t_id)
            db.session.add(pt)
        pt.cantidad = 1000
        pt.precio_venta = 2000
        pt.sync_estado = 'pendiente'
    print("  -> Producto activado y con stock.")
else:
    print("  No se encontró ese código en la Central.")

# 2. Arreglamos el fantasma (ID 2924) para que no estorbe
p_fantasma = Producto.query.filter_by(id=2924).first()
if p_fantasma:
    # Le cambiamos el código falso por uno aún más falso para que no choque
    p_fantasma.codigo_barras = 'BORRAR-DUPLICADO'
    p_fantasma.categoria = 'INACTIVO'
    print("  Fantasma (ID 2924) desactivado y aislado.")

db.session.commit()
print("¡Listo! La Central ya tiene el producto real activo y el fantasma aislado.")
