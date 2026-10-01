# scripts/crear_modelos.py
# Script que genera todos los archivos de modelos SQLAlchemy.
# Ejecutar UNA SOLA VEZ:  python scripts\crear_modelos.py

import os

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'models')
os.makedirs(BASE, exist_ok=True)

ARCHIVOS = {}

# ---------- __init__.py ----------
ARCHIVOS['__init__.py'] = '''# app/models/__init__.py
from .tienda import Tienda
from .usuario import Usuario
from .producto import Producto, ProductoTienda
from .cliente import Cliente
from .factura import Factura, DetalleFactura
from .pago import Pago
from .venta import Venta
from .borrador import Borrador
from .configuracion import Configuracion
from .sync_log import SyncLog

__all__ = [
    'Tienda', 'Usuario',
    'Producto', 'ProductoTienda',
    'Cliente',
    'Factura', 'DetalleFactura',
    'Pago', 'Venta', 'Borrador',
    'Configuracion', 'SyncLog',
]
'''

# ---------- tienda.py ----------
ARCHIVOS['tienda.py'] = '''# app/models/tienda.py
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
'''

# ---------- usuario.py ----------
ARCHIVOS['usuario.py'] = '''# app/models/usuario.py
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), default='operario', nullable=False)
    tienda_id = db.Column(db.Integer, db.ForeignKey('tiendas.id'), nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    tienda = db.relationship('Tienda', back_populates='usuarios')
    facturas = db.relationship('Factura', back_populates='usuario', lazy='dynamic')

    # Helpers de rol
    def es_programador(self):
        return self.rol == 'programador'

    def es_admin(self):
        return self.rol in ('admin', 'programador')

    def es_operario(self):
        return self.rol == 'operario'

    def puede_gestionar_usuarios(self):
        return self.rol == 'programador'

    def puede_ver_estadisticas(self):
        return self.rol in ('admin', 'programador')

    def __repr__(self):
        return f'<Usuario {self.username} ({self.rol})>'
'''

# ---------- producto.py ----------
ARCHIVOS['producto.py'] = '''# app/models/producto.py
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
'''

# ---------- cliente.py ----------
ARCHIVOS['cliente.py'] = '''# app/models/cliente.py
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
'''

# ---------- factura.py ----------
ARCHIVOS['factura.py'] = '''# app/models/factura.py
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
'''

# ---------- pago.py ----------
ARCHIVOS['pago.py'] = '''# app/models/pago.py
from datetime import datetime
from app.extensions import db


class Pago(db.Model):
    __tablename__ = 'pagos'

    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(
        db.Integer,
        db.ForeignKey('facturas.id'),
        nullable=False,
        index=True
    )
    tienda_id = db.Column(db.Integer, db.ForeignKey('tiendas.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    monto = db.Column(db.Numeric(12, 2), nullable=False)
    metodo_pago = db.Column(db.String(20), default='efectivo')

    # Sync
    sync_estado = db.Column(db.String(20), default='pendiente')
    sync_fecha = db.Column(db.DateTime)

    # Relaciones
    factura = db.relationship('Factura', back_populates='pagos')
    tienda = db.relationship('Tienda')

    def __repr__(self):
        return f'<Pago factura={self.factura_id} monto={self.monto}>'
'''

# ---------- venta.py ----------
ARCHIVOS['venta.py'] = '''# app/models/venta.py
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
'''

# ---------- borrador.py ----------
ARCHIVOS['borrador.py'] = '''# app/models/borrador.py
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
'''

# ---------- configuracion.py ----------
ARCHIVOS['configuracion.py'] = '''# app/models/configuracion.py
from app.extensions import db


class Configuracion(db.Model):
    __tablename__ = 'configuracion'

    tienda_id = db.Column(
        db.Integer,
        db.ForeignKey('tiendas.id'),
        primary_key=True,
        nullable=True
    )
    clave = db.Column(db.String(50), primary_key=True)
    valor = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<Config {self.clave}={self.valor}>'
'''

# ---------- sync_log.py ----------
ARCHIVOS['sync_log.py'] = '''# app/models/sync_log.py
from datetime import datetime
from app.extensions import db


class SyncLog(db.Model):
    __tablename__ = 'sync_log'

    id = db.Column(db.Integer, primary_key=True)
    tienda_id = db.Column(db.Integer, db.ForeignKey('tiendas.id'), nullable=False)
    tipo = db.Column(db.String(20))
    tabla = db.Column(db.String(50))
    registros = db.Column(db.Integer, default=0)
    exitoso = db.Column(db.Boolean, default=True)
    mensaje = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<SyncLog {self.tipo} {self.tabla}>'
'''


def main():
    print(f'Creando modelos en: {BASE}')
    print('-' * 60)

    for nombre, contenido in ARCHIVOS.items():
        ruta = os.path.join(BASE, nombre)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f'  OK  {nombre}')

    print('-' * 60)
    print(f'Listo: {len(ARCHIVOS)} archivos creados correctamente.')


if __name__ == '__main__':
    main()