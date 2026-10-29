import sys
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

app = create_app()
with app.app_context():
    codigo = '2001672288329'
    print(f"--- BUSCANDO CUALQUIER RELACION CON {codigo} EN LA CENTRAL ---")
    
    # Buscamos en codigo_barras, imagen, nombre, codigo_global
    productos = Producto.query.filter(
        db.or_(
            Producto.codigo_barras.like(f'%{codigo}%'),
            Producto.imagen.like(f'%{codigo}%'),
            Producto.nombre.like(f'%{codigo}%'),
            Producto.codigo_global.like(f'%{codigo}%')
        )
    ).all()
    
    if not productos:
        print("No se encontro ningun producto relacionado en la Central.")
    else:
        for p in productos:
            print(f"ID: {p.id} | Nombre: {p.nombre}")
            print(f"  Codigo Barras: {p.codigo_barras}")
            print(f"  Imagen: {p.imagen}")
            print(f"  Codigo Global: {p.codigo_global}")
            print(f"  Categoria: {p.categoria}")
            pres = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
            if pres:
                print(f"  Stock T1: {pres.cantidad} | Precio T1: {pres.precio_venta}")
            print("-" * 40)
