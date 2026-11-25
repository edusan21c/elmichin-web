from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from app.extensions import db

app = create_app()
app.app_context().push()

# Buscamos los productos "Frankenstein" (Auto-Fix o código 'Borrar-duplicado')
basura = Producto.query.filter(
    (Producto.nombre.ilike('%Auto-Fix%')) | 
    (Producto.codigo_barras == 'Borrar-duplicado')
).all()

print(f"Se encontraron {len(basura)} productos basura para analizar...")

borrados = 0
protegidos = 0

for p in basura:
    # 1. Candado de Seguridad: ¿Tiene ventas?
    tiene_ventas = DetalleFactura.query.filter_by(producto_id=p.id).first()
    if tiene_ventas:
        print(f"  [Protegido] {p.nombre} - Tiene ventas registradas.")
        protegidos += 1
        continue

    # 2. Candado de Seguridad: ¿Tiene stock en alguna tienda?
    pt_t1 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
    pt_t2 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=2).first()
    stock_t1 = pt_t1.cantidad if pt_t1 else 0
    stock_t2 = pt_t2.cantidad if pt_t2 else 0

    if stock_t1 > 0 or stock_t2 > 0:
        print(f"  [Protegido] {p.nombre} - Tiene stock (T1:{stock_t1}, T2:{stock_t2}).")
        protegidos += 1
        continue

    # Si pasó los candados, es basura pura. ¡A borrar!
    ProductoTienda.query.filter_by(producto_id=p.id).delete()
    db.session.delete(p)
    borrados += 1

db.session.commit()
print("=====================================")
print(f"¡Limpieza terminada!")
print(f"Productos borrados: {borrados}")
print(f"Productos protegidos (tenían ventas o stock): {protegidos}")
