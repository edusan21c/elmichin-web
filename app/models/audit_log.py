# app/models/audit_log.py
from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(100))
    user_nombre = db.Column(db.String(200))
    tienda_id = db.Column(db.Integer)
    accion = db.Column(db.String(50), nullable=False)
    detalle = db.Column(db.Text)
    ip = db.Column(db.String(45))
    user_agent = db.Column(db.String(300))
    fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<AuditLog {self.accion} user={self.username}>'