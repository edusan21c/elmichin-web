# app/models/usuario.py
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
