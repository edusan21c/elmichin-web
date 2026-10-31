from datetime import datetime
from app.extensions import db

class OrdenCompra(db.Model):
    __tablename__ = 'ordenes_compra'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    tienda_id = db.Column(db.Integer, db.ForeignKey('tiendas.id'), nullable=False)
    estado = db.Column(db.String(20), default='pendiente') # pendiente, recibida, cancelada
    total_estimado = db.Column(db.Numeric(12, 2), default=0)
    
    # Relaciones
    tienda = db.relationship('Tienda')
    detalles = db.relationship('DetalleOrdenCompra', backref='orden', cascade='all, delete-orphan')

class DetalleOrdenCompra(db.Model):
    __tablename__ = 'detalles_orden_compra'

    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes_compra.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad_pedida = db.Column(db.Integer, nullable=False)
    cantidad_recibida = db.Column(db.Integer, default=0)
    costo_unitario = db.Column(db.Numeric(12, 2), default=0)

    # Relaciones
    producto = db.relationship('Producto')