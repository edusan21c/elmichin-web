# app/models/tienda.py
from datetime import datetime
from app.extensions import db


class Tienda(db.Model):
    __tablename__ = 'tiendas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(50))
    activa = db.Column(db.Boolean, default=True, nullable=False)
    creada_en = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    usuarios = db.relationship('Usuario', back_populates='tienda', lazy='dynamic')
    clientes = db.relationship('Cliente', back_populates='tienda', lazy='dynamic')
    facturas = db.relationship('Factura', back_populates='tienda', lazy='dynamic')

    def __repr__(self):
        return f'<Tienda {self.nombre}>'
