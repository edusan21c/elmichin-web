from app import create_app
from app.extensions import db
from app.models.factura import Factura
from app.models.pago import Pago
from decimal import Decimal

app = create_app()
app.app_context().push()

print('=== INICIANDO REPARACION HISTORICA DE PAGOS ===')
facturas = Factura.query.all()
creados = 0

for f in facturas:
    if f.valor_pagado and f.valor_pagado > Decimal('0.00'):
        # Verificamos si la factura ya tiene algun pago registrado
        existe_pago = Pago.query.filter_by(factura_id=f.id).first()
        if not existe_pago:
            nuevo_pago = Pago(
                factura_id=f.id,
                tienda_id=f.tienda_id,
                monto=f.valor_pagado,
                metodo_pago='historico',
                origen='local',
                sync_estado='pendiente'
            )
            db.session.add(nuevo_pago)
            creados += 1

db.session.commit()
print(f'=== REPARACION COMPLETA: {creados} pagos historicos creados ===')