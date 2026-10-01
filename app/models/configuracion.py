# app/models/configuracion.py
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
