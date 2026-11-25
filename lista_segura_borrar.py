from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from sqlalchemy import func

app = create_app()
app.app_context().push()

print("==========================================================")
print("   PRODUCTOS SEGUROS DE BORRAR (NO TIENEN VENTAS)         ")
print("==========================================================")

# Buscamos los IDs de todos los productos que SÍ tienen ventas
ids_con_ventas = [r[0] for r in db.session.query(DetalleFactura.producto_id).distinct().all()]

# Buscamos todos los productos que NO estén en esa lista
productos_seguros = Producto.query.filter(~Producto.id.in_(ids_con_ventas)).all()

print(f"Total de productos en el sistema: {Producto.query.count()}")
print(f"Productos con ventas (intocables): {len(ids_con_ventas)}")
print(f"Productos SEGUROS de borrar (sin ventas): {len(productos_seguros)}\n")

print(f"{'ID':<6} | {'NOMBRE':<45} | {'CATEGORIA':<15} | {'STOCK T1':<10} | {'STOCK T2'}")
print("-" * 90)

for p in productos_seguros:
    t1 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
    t2 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=2).first()
    stock1 = t1.cantidad if t1 else 0
    stock2 = t2.cantidad if t2 else 0
    
    # Truncamos el nombre si es muy largo para que se vea bonito en consola
    nombre_corto = (p.nombre[:42] + '...') if len(p.nombre) > 45 else p.nombre
    cat = p.categoria if p.categoria else "Ninguna"
    
    print(f"{p.id:<6} | {nombre_corto:<45} | {cat:<15} | {stock1:<10} | {stock2}")

print("==========================================================")
