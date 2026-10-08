# app/models/pago.py
from datetime import datetime
from app.extensions import db


class Pago(db.Model):
    __tablename__ = 'pagos'

    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(db.Integer, db.ForeignKey('facturas.id'), nullable=False, index=True)
    tienda_id = db.Column(db.Integer, db.ForeignKey('tiendas.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    metodo_pago = db.Column(db.String(20), default='efectivo')

    # Sync
    sync_estado = db.Column(db.String(20), default='pendiente', index=True)
    sync_fecha = db.Column(db.DateTime)
    sync_hash = db.Column(db.String(64), index=True)

    # Origen: 'local' (creado en esta PC) o 'remota' (bajado del central)
    origen = db.Column(db.String(20), default='local', index=True)

    # Relaciones
    factura = db.relationship('Factura', back_populates='pagos')
    tienda = db.relationship('Tienda')

    def __repr__(self):
        return f'<Pago factura={self.factura_id} monto={self.monto} origen={self.origen}>'