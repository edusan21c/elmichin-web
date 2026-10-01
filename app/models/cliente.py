# app/models/cliente.py
from datetime import datetime
from app.extensions import db


class Cliente(db.Model):
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    tienda_id = db.Column(
        db.Integer,
        db.ForeignKey('tiendas.id'),
        nullable=False,
        index=True
    )
    nombre = db.Column(db.String(200), nullable=False, index=True)
    documento = db.Column(db.String(50))
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(50))
    email = db.Column(db.String(100))
    saldo_actual = db.Column(db.Numeric(12, 2), default=0)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    # Sync
    sync_estado = db.Column(db.String(20), default='pendiente')
    sync_fecha = db.Column(db.DateTime)

    # Relaciones
    tienda = db.relationship('Tienda', back_populates='clientes')
    facturas = db.relationship('Factura', back_populates='cliente', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tienda_id', 'documento', name='uq_cliente_tienda_doc'),
    )

    def __repr__(self):
        return f'<Cliente {self.nombre} (tienda {self.tienda_id})>'
