# app/services/auditoria_service.py
"""Servicio de auditoría: registra acciones de usuarios."""
from datetime import datetime
from flask import request
from flask_login import current_user
from app.extensions import db
from app.models.audit_log import AuditLog


def registrar_auditoria(accion, detalle='', tienda_id=None):
    """
    Registra una acción en el log de auditoría.
    - accion: string corto (ej: 'login', 'factura_crear', 'abono_registrar')
    - detalle: texto libre con info adicional
    """
    try:
        user_id = None
        username = 'anonimo'
        user_nombre = ''
        if current_user and current_user.is_authenticated:
            user_id = current_user.id
            username = current_user.username
            user_nombre = current_user.nombre or ''
            if tienda_id is None:
                tienda_id = current_user.tienda_id

        ip = ''
        user_agent = ''
        try:
            ip = request.headers.get('X-Forwarded-For', request.remote_addr or '')
            ip = ip.split(',')[0].strip()[:45]
            user_agent = (request.headers.get('User-Agent') or '')[:300]
        except Exception:
            pass

        log = AuditLog(
            user_id=user_id,
            username=username,
            user_nombre=user_nombre,
            tienda_id=tienda_id,
            accion=accion,
            detalle=(detalle or '')[:2000],
            ip=ip,
            user_agent=user_agent,
            fecha=datetime.utcnow(),
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'[auditoria] error: {e}')