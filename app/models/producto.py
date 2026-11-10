# app/models/producto.py
from datetime import datetime
from app.extensions import db
from sqlalchemy.orm import validates

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), unique=True, nullable=False, index=True)
    codigo_barras = db.Column(db.String(50), unique=True, index=True)
    codigo_global = db.Column(db.String(36), unique=True, index=True, nullable=True)
    categoria = db.Column(db.String(50))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    modificado_por_nombre = db.Column(db.String(100), nullable=True)
    modificado_en = db.Column(db.DateTime, nullable=True)
    imagen = db.Column(db.String(255), nullable=True)

    presentaciones = db.relationship('ProductoTienda', back_populates='producto', cascade='all, delete-orphan', lazy='dynamic')

    def get_presentacion(self, tienda_id):
        return ProductoTienda.query.filter_by(producto_id=self.id, tienda_id=tienda_id).first()

    def __repr__(self):
        return f'<Producto {self.nombre}>'

    # ==========================================
    # 🛡️ GUARDIANES DE INTEGRIDAD (Validadores)
    # ==========================================
    
    @validates('nombre')
    def validar_nombre(self, key, value):
        if not value:
            raise ValueError("El nombre del producto no puede estar vacío.")
        
        value = value.strip() # Quitar espacios en blanco al inicio y final
        
        # Verificar si el nombre ya existe en OTRO producto
        existente = Producto.query.filter(
            Producto.nombre == value, 
            Producto.id != self.id
        ).first()
        
        if existente:
            raise ValueError(f"❌ BLOQUEADO: Ya existe un producto con el nombre '{value}' (ID: {existente.id}).")
        return value

    @validates('codigo_barras')
    def validar_codigo_barras(self, key, value):
        if not value:
            return value # Permitir códigos vacíos
            
        value = value.strip()
        
        # Si el producto ya está guardado y el código no cambió, no validar de nuevo
        if self.id and self.codigo_barras == value:
            return value
            
        # Evitar la creación de códigos basura del POS (solo si es producto nuevo)
        if not self.id:
            if value.startswith('200') and len(value) > 10:
                raise ValueError(f"❌ BLOQUEADO: No se permite crear productos con código de emergencia POS ('200...').")
            if value.startswith('AUTO-'):
                raise ValueError(f"❌ BLOQUEADO: No se permite crear productos con código automático ('AUTO-...').")
                
        # Verificar si el código ya existe en OTRO producto
        existente = Producto.query.filter(
            Producto.codigo_barras == value, 
            Producto.id != self.id
        ).first()
        
        if existente:
            raise ValueError(f"❌ BLOQUEADO: El código de barras '{value}' ya pertenece al producto '{existente.nombre}' (ID: {existente.id}).")
        return value


class ProductoTienda(db.Model):
    __tablename__ = 'producto_tienda'

    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id', ondelete='CASCADE'), primary_key=True)
    tienda_id = db.Column(db.Integer, db.ForeignKey('tiendas.id', ondelete='CASCADE'), primary_key=True)

    cantidad = db.Column(db.Integer, nullable=False, default=0)
    stock_minimo = db.Column(db.Integer, default=5)
    stock_maximo = db.Column(db.Integer, default=20)

    # Aquí usamos las 3 columnas existentes para los 3 proveedores
    precio_proveedor = db.Column(db.Numeric(12, 2), default=0) # Prov 1
    precio_proveedor2 = db.Column(db.Numeric(12, 2), default=0) # Prov 2
    precio_proveedor3 = db.Column(db.Numeric(12, 2), default=0) # Prov 3

    porcentaje = db.Column(db.Numeric(6, 2), default=0)
    precio_venta = db.Column(db.Numeric(12, 2), default=0)

    descuento1_porcentaje = db.Column(db.Numeric(6, 2), default=0)
    precio_venta1 = db.Column(db.Numeric(12, 2), default=0)
    descuento2_porcentaje = db.Column(db.Numeric(6, 2), default=0)
    precio_venta2 = db.Column(db.Numeric(12, 2), default=0)
    descuento3_porcentaje = db.Column(db.Numeric(6, 2), default=0)
    precio_venta3 = db.Column(db.Numeric(12, 2), default=0)

    condicion1 = db.Column(db.String(10), default='')
    condicion2 = db.Column(db.String(10), default='')
    condicion3 = db.Column(db.String(10), default='')

    sync_estado = db.Column(db.String(20), default='pendiente', index=True)
    sync_fecha = db.Column(db.DateTime)
    sync_hash = db.Column(db.String(64))

    producto = db.relationship('Producto', back_populates='presentaciones')
    tienda = db.relationship('Tienda')

    __table_args__ = (db.Index('idx_prod_tienda_stock', 'tienda_id', 'cantidad'),)

    def calcular_precio(self, cantidad):
        cant = int(cantidad)
        def _parse(v):
            try: return int(v) if v else None
            except: return None
        cond1, cond2, cond3 = _parse(self.condicion1), _parse(self.condicion2), _parse(self.condicion3)
        if cond3 and cant >= cond3 and self.precio_venta3 and self.precio_venta3 > 0: return float(self.precio_venta3)
        if cond2 and cant >= cond2 and self.precio_venta2 and self.precio_venta2 > 0: return float(self.precio_venta2)
        if cond1 and cant >= cond1 and self.precio_venta1 and self.precio_venta1 > 0: return float(self.precio_venta1)
        return float(self.precio_venta or 0)

    def __repr__(self):
        return f'<ProductoTienda p={self.producto_id} t={self.tienda_id} stock={self.cantidad}>'


class Ensamble(db.Model):
    __tablename__ = 'ensambles'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    origen_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    cantidad_origen = db.Column(db.Integer) # Cuántas unidades se sacaron
    destino_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    cantidad_destino = db.Column(db.Integer) # Cuántos paquetes se armaron

    def __repr__(self):
        return f'<Ensamble ori={self.origen_id} dest={self.destino_id}>'