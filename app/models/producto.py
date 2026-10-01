# app/models/producto.py
from datetime import datetime
from app.extensions import db


class Producto(db.Model):
    """Catalogo global de productos (compartido entre tiendas)."""
    __tablename__ = 'productos'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), unique=True, nullable=False, index=True)
    codigo_barras = db.Column(db.String(50), unique=True, index=True)
    categoria = db.Column(db.String(50))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    presentaciones = db.relationship(
        'ProductoTienda',
        back_populates='producto',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    def get_presentacion(self, tienda_id):
        """Devuelve la presentacion (precios/stock) para una tienda."""
        return ProductoTienda.query.filter_by(
            producto_id=self.id, tienda_id=tienda_id
        ).first()

    def __repr__(self):
        return f'<Producto {self.nombre}>'


class ProductoTienda(db.Model):
    """Presentacion comercial del producto en cada tienda."""
    __tablename__ = 'producto_tienda'

    producto_id = db.Column(
        db.Integer,
        db.ForeignKey('productos.id', ondelete='CASCADE'),
        primary_key=True
    )
    tienda_id = db.Column(
        db.Integer,
        db.ForeignKey('tiendas.id', ondelete='CASCADE'),
        primary_key=True
    )

    # Stock
    cantidad = db.Column(db.Integer, nullable=False, default=0)

    # Precios de proveedor
    precio_proveedor = db.Column(db.Numeric(12, 2), default=0)
    precio_proveedor2 = db.Column(db.Numeric(12, 2), default=0)
    precio_proveedor3 = db.Column(db.Numeric(12, 2), default=0)

    # Precio de venta base
    porcentaje = db.Column(db.Numeric(6, 2), default=0)
    precio_venta = db.Column(db.Numeric(12, 2), default=0)

    # Descuentos por cantidad
    descuento1_porcentaje = db.Column(db.Numeric(6, 2), default=0)
    precio_venta1 = db.Column(db.Numeric(12, 2), default=0)
    descuento2_porcentaje = db.Column(db.Numeric(6, 2), default=0)
    precio_venta2 = db.Column(db.Numeric(12, 2), default=0)
    descuento3_porcentaje = db.Column(db.Numeric(6, 2), default=0)
    precio_venta3 = db.Column(db.Numeric(12, 2), default=0)

    # Condiciones (cantidad minima para el descuento)
    condicion1 = db.Column(db.String(10), default='')
    condicion2 = db.Column(db.String(10), default='')
    condicion3 = db.Column(db.String(10), default='')

    # Sync
    sync_estado = db.Column(db.String(20), default='pendiente', index=True)
    sync_fecha = db.Column(db.DateTime)
    sync_hash = db.Column(db.String(64))

    # Relaciones
    producto = db.relationship('Producto', back_populates='presentaciones')
    tienda = db.relationship('Tienda')

    __table_args__ = (
        db.Index('idx_prod_tienda_stock', 'tienda_id', 'cantidad'),
    )

    def calcular_precio(self, cantidad):
        """Calcula precio unitario aplicando descuentos por volumen."""
        cant = int(cantidad)

        def _parse(v):
            try:
                return int(v) if v else None
            except (ValueError, TypeError):
                return None

        cond1 = _parse(self.condicion1)
        cond2 = _parse(self.condicion2)
        cond3 = _parse(self.condicion3)

        if cond3 and cant >= cond3 and self.precio_venta3 and self.precio_venta3 > 0:
            return float(self.precio_venta3)
        if cond2 and cant >= cond2 and self.precio_venta2 and self.precio_venta2 > 0:
            return float(self.precio_venta2)
        if cond1 and cant >= cond1 and self.precio_venta1 and self.precio_venta1 > 0:
            return float(self.precio_venta1)
        return float(self.precio_venta or 0)

    def __repr__(self):
        return f'<ProductoTienda p={self.producto_id} t={self.tienda_id} stock={self.cantidad}>'
