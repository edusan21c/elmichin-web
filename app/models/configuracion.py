# app/models/configuracion.py
from app.extensions import db


class Configuracion(db.Model):
    __tablename__ = 'configuracion'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tienda_id = db.Column(
        db.Integer,
        db.ForeignKey('tiendas.id'),
        nullable=True
    )
    clave = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.String(200), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('tienda_id', 'clave', name='configuracion_tienda_clave_unique'),
    )

    def __repr__(self):
        return f'<Config {self.clave}={self.valor}>'