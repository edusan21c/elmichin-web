# app/models/factura.py
from datetime import datetime
from app.extensions import db


class Factura(db.Model):
    __tablename__ = 'facturas'

    id = db.Column(db.Integer, primary_key=True)
    numero_factura = db.Column(db.String(20), nullable=False)
    tienda_id = db.Column(
        db.Integer,
        db.ForeignKey('tiendas.id'),
        nullable=False,
        index=True
    )
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    total = db.Column(db.Numeric(12, 2), nullable=False)
    metodo_pago = db.Column(db.String(20), default='')
    recargo_nequi = db.Column(db.Numeric(12, 2), default=0)
    recargo_bolsa = db.Column(db.Numeric(12, 2), default=0)

    valor_pagado = db.Column(db.Numeric(12, 2), default=0)
    vueltas = db.Column(db.Numeric(12, 2), default=0)
    tipo_pago = db.Column(db.String(20), default='contado')
    estado_credito = db.Column(db.String(20), default='pagado')
    saldo_pendiente = db.Column(db.Numeric(12, 2), default=0)
    fecha_vencimiento = db.Column(db.Date)

    # Sync
    sync_estado = db.Column(db.String(20), default='pendiente', index=True)
    sync_fecha = db.Column(db.DateTime)
    sync_hash = db.Column(db.String(64))

    # Relaciones
    tienda = db.relationship('Tienda', back_populates='facturas')
    cliente = db.relationship('Cliente', back_populates='facturas')
    usuario = db.relationship('Usuario', back_populates='facturas')
    detalles = db.relationship(
        'DetalleFactura',
        back_populates='factura',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    pagos = db.relationship(
        'Pago',
        back_populates='factura',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    __table_args__ = (
        db.UniqueConstraint('tienda_id', 'numero_factura', name='uq_factura_tienda_num'),
        db.Index('idx_facturas_tienda_fecha', 'tienda_id', 'fecha_hora'),
    )

    def __repr__(self):
        return f'<Factura {self.numero_factura} (tienda {self.tienda_id})>'


class DetalleFactura(db.Model):
    __tablename__ = 'detalle_factura'

    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(
        db.Integer,
        db.ForeignKey('facturas.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    producto_nombre = db.Column(db.String(200), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)

    # Relaciones
    factura = db.relationship('Factura', back_populates='detalles')
    producto = db.relationship('Producto')

    __table_args__ = (
        db.Index('idx_detalle_factura', 'factura_id'),
        db.Index('idx_detalle_producto', 'producto_id'),
    )

    def __repr__(self):
        return f'<DetalleFactura factura={self.factura_id}>'
