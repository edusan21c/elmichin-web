from app import create_app
from app.extensions import db
from app.models.cliente import Cliente
from app.models.factura import Factura
from decimal import Decimal

app = create_app()
app.app_context().push()

print("=== CORRIGIENDO TIENDA_ID DE LOS CLIENTES ===")
clientes = Cliente.query.all()
movidos = 0

for c in clientes:
    if c.saldo_actual > Decimal('0.00'):
        facturas = Factura.query.filter_by(cliente_id=c.id).all()
        tiendas_facturas = set(f.tienda_id for f in facturas if f.tienda_id is not None)
        
        if 2 in tiendas_facturas and c.tienda_id != 2:
            print(f"Moviendo a {c.nombre} a Tienda 2 (antes estaba en Tienda {c.tienda_id})")
            c.tienda_id = 2
            movidos += 1

db.session.commit()
print(f"Clientes movidos a su tienda correcta: {movidos}")