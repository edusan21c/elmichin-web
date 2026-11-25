from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from app.extensions import db

app = create_app()
app.app_context().push()

inactivos = Producto.query.filter_by(categoria='INACTIVO').all()

reutilizables = []

for p in inactivos:
    # 1. Candado: ¿Tiene ventas?
    tiene_ventas = DetalleFactura.query.filter_by(producto_id=p.id).first() is not None
    
    # 2. Candado: ¿Tiene stock?
    pt_t1 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
    pt_t2 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=2).first()
    stock1 = pt_t1.cantidad if pt_t1 else 0
    stock2 = pt_t2.cantidad if pt_t2 else 0
    tiene_stock = (stock1 > 0) or (stock2 > 0)

    # Si NO tiene ventas y NO tiene stock, es seguro reutilizarlo
    if not tiene_ventas and not tiene_stock:
        reutilizables.append(p)

print("=========================================================")
print(f"   PRODUCTOS LISTOS PARA REUTILIZAR (Total: {len(reutilizables)})")
print("=========================================================")

for p in reutilizables:
    foto = "CON FOTO" if p.imagen else "SIN FOTO"
    print(f"  - ID: {p.id} | Nombre: {p.nombre} | {foto}")

print("=========================================================")
