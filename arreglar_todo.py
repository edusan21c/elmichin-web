from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- RESTAURANDO PRODUCTOS CLAVE EN LA CENTRAL ---")

# 1. ARREGLAR EL AGUA CIELO
p_agua = Producto.query.filter_by(id=2924).first()
if p_agua:
    p_agua.nombre = 'Un. Agua Cielo 1000mL Chupo'
    p_agua.codigo_barras = '77072445612'
    p_agua.categoria = 'bebida'
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_agua.id, tienda_id=t_id).first()
        if not pt:
            pt = ProductoTienda(producto_id=p_agua.id, tienda_id=t_id)
            db.session.add(pt)
        pt.cantidad = 1000
        pt.precio_venta = 2000
        pt.sync_estado = 'pendiente'
    print("  Agua Cielo corregida y activada.")
else:
    print("  No se encontró el Agua Cielo en la Central.")

# 2. CREAR/RESTAURAR LOS TRULULUS FALTANTES
# Diccionario con los nombres exactos y códigos de barras reales de la Tienda 1
trucos = {
    'B. Trululu Caramelo Salado 100g 54g': '7702993060308',
    'B. Trululu Helado Fresa 100g 54g': '7702993056714',
    'B. Trululu Masmelos Choco Banana 100g 50g': '7702993052297'
}

for nombre, codigo in trucos.items():
    # Buscamos si ya existe por código de barras
    p = Producto.query.filter_by(codigo_barras=codigo).first()
    if not p:
        # Si no existe, lo creamos
        p = Producto(nombre=nombre, codigo_barras=codigo, categoria='dulces')
        db.session.add(p)
        db.session.flush()
    else:
        # Si existe, lo actualizamos
        p.nombre = nombre
        p.categoria = 'dulces'
    
    # Le asignamos stock y precio
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=t_id).first()
        if not pt:
            pt = ProductoTienda(producto_id=p.id, tienda_id=t_id)
            db.session.add(pt)
        pt.cantidad = 100
        pt.precio_venta = 3000
        pt.sync_estado = 'pendiente'
        
    print(f"  Creado/Actualizado: {nombre}")

db.session.commit()
print("¡Listo! Todos los productos restaurados en la Central.")
