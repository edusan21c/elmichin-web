# app/models/sync_log.py
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
