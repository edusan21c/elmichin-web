from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# Buscamos el Volcan sin importar si tiene espacios raros
p = Producto.query.filter(Producto.nombre.ilike('%Volcan%')).first()

if p:
    # Le ponemos el nombre exacto, sin espacios extra
    p.nombre = 'B. Trululu Volcan Chocolate 100g 54g'
    p.categoria = 'dulces'
    
    # Lo marcamos para sincronizar
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=t_id).first()
        if pt:
            pt.sync_estado = 'pendiente'
            
    db.session.commit()
    print(f"¡Volcan corregido! ID: {p.id} | Nombre exacto: '{p.nombre}' | Cat: {p.categoria}")
else:
    print("No se encontró el Volcan en la base de datos.")
