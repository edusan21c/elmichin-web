from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from app.extensions import db

app = create_app()
app.app_context().push()

# Buscamos todos los productos cuyo código de barras empiece con "AUTO-"
autos = Producto.query.filter(Producto.codigo_barras.ilike('AUTO-%')).all()

seguros_borrar = []
protegidos = []

for p in autos:
    # 1. Candado: ¿Tiene ventas?
    tiene_ventas = DetalleFactura.query.filter_by(producto_id=p.id).first() is not None
    
    # 2. Candado: ¿Tiene stock?
    pt_t1 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
    pt_t2 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=2).first()
    stock1 = pt_t1.cantidad if pt_t1 else 0
    stock2 = pt_t2.cantidad if pt_t2 else 0
    tiene_stock = (stock1 > 0) or (stock2 > 0)

    # 3. Candado: ¿Tiene foto?
    tiene_foto = bool(p.imagen and p.imagen.strip() and p.imagen != 'error.png')

    if tiene_ventas or tiene_stock or tiene_foto:
        motivo = []
        if tiene_ventas: motivo.append("Tiene ventas")
        if tiene_stock: motivo.append(f"Tiene stock (T1:{stock1}, T2:{stock2})")
        if tiene_foto: motivo.append("Tiene foto")
        protegidos.append((p.id, p.nombre, p.codigo_barras, " y ".join(motivo)))
    else:
        seguros_borrar.append((p.id, p.nombre, p.codigo_barras))

print("=========================================================")
print(f"   ANALISIS DE CODIGOS 'AUTO-' (Total: {len(autos)})")
print("=========================================================")

print(f"\n✅ SEGUROS DE BORRAR (Sin ventas, sin stock, SIN FOTO): {len(seguros_borrar)}")
for id_p, nom, cod in seguros_borrar:
    print(f"  - ID: {id_p} | {nom} | Cod: {cod}")

print(f"\n🛑 PROTEGIDOS (Tienen ventas, stock o FOTO): {len(protegidos)}")
for id_p, nom, cod, motivo in protegidos:
    print(f"  - ID: {id_p} | {nom} | Motivo: {motivo}")

print("=========================================================")
