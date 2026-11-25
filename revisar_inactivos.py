from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from app.extensions import db

app = create_app()
app.app_context().push()

inactivos = Producto.query.filter_by(categoria='INACTIVO').all()

seguros = []
peligrosos = []

for p in inactivos:
    # 1. Candado: ¿Tiene ventas?
    tiene_ventas = DetalleFactura.query.filter_by(producto_id=p.id).first() is not None
    
    # 2. Candado: ¿Tiene stock?
    pt_t1 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
    pt_t2 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=2).first()
    stock1 = pt_t1.cantidad if pt_t1 else 0
    stock2 = pt_t2.cantidad if pt_t2 else 0
    tiene_stock = (stock1 > 0) or (stock2 > 0)

    # 3. Candado NUEVO: ¿Tiene foto?
    tiene_foto = bool(p.imagen and p.imagen.strip() and p.imagen != 'error.png')

    if tiene_ventas or tiene_stock or tiene_foto:
        motivo = []
        if tiene_ventas: motivo.append("Tiene ventas")
        if tiene_stock: motivo.append(f"Tiene stock (T1:{stock1}, T2:{stock2})")
        if tiene_foto: motivo.append("Tiene foto")
        peligrosos.append((p.id, p.nombre, " y ".join(motivo)))
    else:
        seguros.append((p.id, p.nombre))

print("=========================================================")
print(f"   ANALISIS DE INACTIVOS (Total: {len(inactivos)})")
print("=========================================================")

print(f"\n✅ SEGUROS DE BORRAR (Sin ventas, sin stock, SIN FOTO): {len(seguros)}")
for id_p, nom in seguros:
    print(f"  - ID: {id_p} | {nom}")

print(f"\n🛑 PROTEGIDOS (Tienen ventas, stock o FOTO): {len(peligrosos)}")
# Mostramos solo los primeros 20 para que la pantalla no se llene
for id_p, nom, motivo in peligrosos[:20]: 
    print(f"  - ID: {id_p} | {nom} | Motivo: {motivo}")
if len(peligrosos) > 20:
    print(f"  ... y {len(peligrosos) - 20} mas.")

print("=========================================================")
