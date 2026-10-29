import sys
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

app = create_app()
with app.app_context():
    codigo = '2001672288329'
    p = Producto.query.filter_by(codigo_barras=codigo).first()
    
    if p:
        print(f"--- ¡ENCONTRADO EN LA TIENDA 1! ---")
        print(f"ID: {p.id}")
        print(f"Nombre: {p.nombre}")
        print(f"Categoría: {p.categoria}")
        print(f"Imagen: {p.imagen}")
        
        pres = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
        if pres:
            print(f"Stock en T1: {pres.cantidad}")
            print(f"Precio: ")
            print(f"Estado Sync: {pres.sync_estado}")
    else:
        print(f"El producto {codigo} tampoco existe en la Tienda 1.")
