from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("=== A) PRODUCTOS INVOLUCRADOS ===")
ids = [2296, 2613, 2943]
for pid in ids:
    p = Producto.query.get(pid)
    if p:
        print(f"id={p.id} | code={p.codigo_barras} | cat={p.categoria} | {p.nombre}")

print("\n=== B) TODOS los H&S Rosado ===")
for p in Producto.query.filter(Producto.nombre.ilike('%H&S%Rosado%')).all():
    print(f"id={p.id} | code={p.codigo_barras} | cat={p.categoria} | '{p.nombre}'")

print("\n=== C) EL CÓDIGO REAL DEL H&S ROSADO (7501065922243) ===")
for p in Producto.query.filter_by(codigo_barras='7501065922243').all():
    print(f"id={p.id} | cat={p.categoria} | '{p.nombre}'")

print("\n=== D) L&M + Unicornio: estado de sync por tienda ===")
for code in ['a402158b3c15', '7702993056745']:
    p = Producto.query.filter_by(codigo_barras=code).first()
    if not p:
        print(f"[{code}] no existe")
        continue
    print(f"[{code}] id={p.id} '{p.nombre}'")
    for pt in ProductoTienda.query.filter_by(producto_id=p.id).all():
        print(f"   tienda={pt.tienda_id} | sync={pt.sync_estado} | stock={pt.cantidad} | precio={pt.precio_venta}")

print("\n=== E) CONFLICTO 2613: ¿tenía stock o ventas? ===")
for pt in ProductoTienda.query.filter_by(producto_id=2613).all():
    print(f"   tienda={pt.tienda_id} | stock={pt.cantidad} | sync={pt.sync_estado}")

print("\n=== F) Mapa real de tienda_id ===")
for row in db.session.execute(db.text("SELECT tienda_id, COUNT(*) AS n FROM producto_tienda GROUP BY tienda_id ORDER BY tienda_id")).all():
    print(f"   tienda_id={row[0]} | {row[1]} filas")
