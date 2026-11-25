from app import create_app
from app.models.producto import Producto
from app.models.factura import DetalleFactura
from app.extensions import db
from sqlalchemy import desc

app = create_app()
app.app_context().push()

print("--- BUSCANDO EL ÚLTIMO PRECIO DE VENTA REAL EN EL HISTORIAL ---")

# 1. Buscamos el L&M
p_lm = Producto.query.get(1373)
if p_lm:
    detalle_lm = DetalleFactura.query.filter_by(producto_id=p_lm.id).order_by(desc(DetalleFactura.id)).first()
    if detalle_lm:
        print(f"L&M (ID 1373): Último precio de venta registrado = ${detalle_lm.precio_unitario}")
    else:
        print("L&M (ID 1373): No tiene ventas registradas en el historial.")

# 2. Buscamos el H&S
p_hs = Producto.query.get(2943)
if p_hs:
    detalle_hs = DetalleFactura.query.filter_by(producto_id=p_hs.id).order_by(desc(DetalleFactura.id)).first()
    if detalle_hs:
        print(f"H&S (ID 2943): Último precio de venta registrado = ${detalle_hs.precio_unitario}")
    else:
        print("H&S (ID 2943): No tiene ventas registradas en el historial.")
