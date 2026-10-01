# app/models/borrador.py
from datetime import datetime
from app.extensions import db


class Borrador(db.Model):
    __tablename__ = 'borradores'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20))
    tienda_id = db.Column(db.Integer, db.ForeignKey('tiendas.id'), nullable=False)
    carrito_json = db.Column(db.Text, nullable=False)
    cliente_nombre = db.Column(db.String(200))
    cliente_documento = db.Column(db.String(50))
    cliente_direccion = db.Column(db.String(200))
    cliente_telefono = db.Column(db.String(50))
    cliente_email = db.Column(db.String(100))
    metodo_pago = db.Column(db.String(20))
    bolsa_cantidad = db.Column(db.Integer)
    fecha_guardado = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Borrador {self.tipo} tienda={self.tienda_id}>'
