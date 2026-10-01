# app/models/venta.py
from datetime import datetime
from app.extensions import db


class Venta(db.Model):
    __tablename__ = 'ventas'

    id = db.Column(db.Integer, primary_key=True)
    tienda_id = db.Column(
        db.Integer,
        db.ForeignKey('tiendas.id'),
        nullable=False,
        index=True
    )
    fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(12, 2))
    total = db.Column(db.Numeric(12, 2))

    # Sync
    sync_estado = db.Column(db.String(20), default='pendiente')
    sync_fecha = db.Column(db.DateTime)

    # Relaciones
    tienda = db.relationship('Tienda')
    producto = db.relationship('Producto')

    def __repr__(self):
        return f'<Venta producto={self.producto_id} cant={self.cantidad}>'
