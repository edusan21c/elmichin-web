# app/blueprints/admin/auditoria.py
from datetime import datetime, timedelta
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.tienda import Tienda
from app.utils.decorators import admin_requerido


def hora_local():
    return datetime.utcnow() - timedelta(hours=5)


# ==================== PÁGINA ====================
@bp.route('/auditoria')
@login_required
@admin_requerido
def auditoria():
    tienda_id = None
    if not current_user.es_programador():
        tienda_id = current_user.tienda_id

    tiendas = Tienda.query.filter_by(activa=True).all() if current_user.es_programador() else []

    return render_template(
        'admin/auditoria.html',
        tiendas=tiendas,
        tienda_id=tienda_id,
    )


# ==================== API: DATOS ====================
@bp.route('/api/auditoria')
@login_required
@admin_requerido
def api_auditoria():
    """Devuelve registros de auditoría con filtros."""
    desde_str = request.args.get('desde', '', type=str).strip()
    hasta_str = request.args.get('hasta', '', type=str).strip()
    username = request.args.get('username', '', type=str).strip()
    accion = request.args.get('accion', '', type=str).strip()
    tienda_id = request.args.get('tienda', type=int)

    # Fechas por defecto: hoy
    hoy = hora_local().date()
    if not desde_str:
        desde_str = hoy.strftime('%Y-%m-%d')
    if not hasta_str:
        hasta_str = hoy.strftime('%Y-%m-%d')

    try:
        desde = datetime.strptime(desde_str, '%Y-%m-%d') + timedelta(hours=5)
        hasta = datetime.strptime(hasta_str, '%Y-%m-%d') + timedelta(days=1, hours=5)
    except ValueError:
        desde = datetime.combine(hoy, datetime.min.time()) + timedelta(hours=5)
        hasta = desde + timedelta(days=1)

    # Si no es programador, restringir a su tienda
    if not current_user.es_programador():
        tienda_id = current_user.tienda_id

    q = AuditLog.query.filter(
        AuditLog.fecha >= desde,
        AuditLog.fecha < hasta,
    )
    if username:
        q = q.filter(AuditLog.username.ilike(f'%{username}%'))
    if accion:
        q = q.filter(AuditLog.accion == accion)
    if tienda_id:
        q = q.filter(AuditLog.tienda_id == tienda_id)

    logs = q.order_by(AuditLog.fecha.desc()).limit(500).all()

    # Lista de acciones únicas para el filtro
    acciones_disponibles = [r[0] for r in
        db.session.query(AuditLog.accion).distinct().all() if r[0]]

    return jsonify({
        'ok': True,
        'total': len(logs),
        'logs': [{
            'id': l.id,
            'fecha': (l.fecha - timedelta(hours=5)).strftime('%d/%m/%Y %H:%M:%S'),
            'username': l.username or '—',
            'user_nombre': l.user_nombre or '',
            'tienda_id': l.tienda_id,
            'accion': l.accion,
            'detalle': l.detalle or '',
            'ip': l.ip or '',
        } for l in logs],
        'acciones': sorted(acciones_disponibles),
    })