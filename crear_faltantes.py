from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- CREANDO LOS 3 TRULULUS FALTANTES ---")

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
        print(f"  Creado: {nombre}")
    else:
        # Si existe, le actualizamos el nombre
        p.nombre = nombre
        p.categoria = 'dulces'
        print(f"  Actualizado: {nombre}")

    # Le asignamos stock y precio
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=t_id).first()
        if not pt:
            pt = ProductoTienda(producto_id=p.id, tienda_id=t_id)
            db.session.add(pt)
        pt.cantidad = 100
        pt.precio_venta = 3000
        pt.sync_estado = 'pendiente'

db.session.commit()
print("¡Listo! Los 3 productos han sido creados y guardados en la Central.")
