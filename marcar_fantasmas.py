from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from app.extensions import db

app = create_app()
app.app_context().push()

# Buscamos todos los productos ACTIVOS que tengan ventas
productos = Producto.query.filter(Producto.categoria != 'INACTIVO').all()

fantasmas_marcados = 0

print("Buscando fantasmas (Precio $0, Stock 0, pero con ventas)...")

for p in productos:
    # Verificamos stock y precio
    pt_t1 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
    stock1 = pt_t1.cantidad if pt_t1 else 0
    
    precio1 = float(pt_t1.precio_venta) if pt_t1 and pt_t1.precio_venta else 0
    
    # Verificamos si tiene ventas
    tiene_ventas = DetalleFactura.query.filter_by(producto_id=p.id).first() is not None
    
    # Si tiene ventas, stock 0 y precio 0, es un fantasma
    if tiene_ventas and stock1 == 0 and precio1 == 0:
        # Si no tiene ya la etiqueta, se la ponemos
        if not p.nombre.startswith('[GHOST]'):
            p.nombre = f"[GHOST] {p.nombre}"
            fantasmas_marcados += 1
            print(f"  Marcado: {p.nombre}")

db.session.commit()
print("=====================================")
print(f"Total de fantasmas marcados: {fantasmas_marcados}")
print("Los cajeros ahora sabrán que no deben venderlos.")
