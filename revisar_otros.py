from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from app.extensions import db

app = create_app()
app.app_context().push()

# Buscamos todos los productos en la categoría 'otro'
productos_otro = Producto.query.filter_by(categoria='otro').all()

seguros = []
peligrosos = []

print("=========================================================")
print(f"   ANALISIS DE CATEGORIA 'OTRO' (Total: {len(productos_otro)})")
print("=========================================================")

for p in productos_otro:
    # 1. Candado: ¿Tiene ventas?
    tiene_ventas = DetalleFactura.query.filter_by(producto_id=p.id).first() is not None
    
    # 2. Candado: ¿Tiene stock?
    pt_t1 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
    pt_t2 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=2).first()
    stock1 = pt_t1.cantidad if pt_t1 else 0
    stock2 = pt_t2.cantidad if pt_t2 else 0
    tiene_stock = (stock1 > 0) or (stock2 > 0)

    if tiene_ventas or tiene_stock:
        motivo = []
        if tiene_ventas: motivo.append("Tiene ventas")
        if tiene_stock: motivo.append(f"Tiene stock (T1:{stock1}, T2:{stock2})")
        peligrosos.append((p.id, p.nombre, " y ".join(motivo)))
    else:
        seguros.append((p.id, p.nombre))

print(f"\n✅ SEGUROS DE BORRAR (Sin ventas, sin stock): {len(seguros)}")
for id_p, nom in seguros:
    print(f"  - ID: {id_p} | {nom}")

print(f"\n🛑 PROTEGIDOS (Tienen ventas o stock): {len(peligrosos)}")
for id_p, nom, motivo in peligrosos:
    print(f"  - ID: {id_p} | {nom} | Motivo: {motivo}")

print("=========================================================")
