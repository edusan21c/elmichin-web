from app import create_app
from app.extensions import db
from app.models.producto import Producto
from app.models.factura import DetalleFactura

app = create_app()
app.app_context().push()

print("==================================================")
print("   SIMULACION DE BORRADO (NO SE BORRARA NADA)     ")
print("==================================================")

inactivos = Producto.query.filter_by(categoria='INACTIVO').all()
seguros = 0
protegidos = 0

for p in inactivos:
    tiene_ventas = DetalleFactura.query.filter_by(producto_id=p.id).first()
    if tiene_ventas:
        protegidos += 1
    else:
        seguros += 1
        print(f"Se podria borrar: {p.id} - {p.nombre}")

print("--------------------------------------------------")
print(f"Total inactivos con ventas (NO se pueden borrar): {protegidos}")
print(f"Total inactivos sin ventas (SEGUROS de borrar): {seguros}")
print("==================================================")
print("RECUERDA: Esto fue solo una simulacion. Nada se ha borrado.")
