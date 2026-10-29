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
        print(f"--- PRODUCTO ENCONTRADO EN CENTRAL ---")
        print(f"ID: {p.id}")
        print(f"Nombre: {p.nombre}")
        print(f"Categoría: {p.categoria}")
        print(f"Imagen: {p.imagen}")
        print("-" * 40)
        
        pres = ProductoTienda.query.filter_by(producto_id=p.id).all()
        for t in pres:
            print(f"Tienda ID: {t.tienda_id}")
            print(f"  Stock: {t.cantidad}")
            print(f"  Precio Venta: ")
            print(f"  Estado Sync: {t.sync_estado}")
    else:
        print(f"El producto con código {codigo} NO existe en la Central.")
