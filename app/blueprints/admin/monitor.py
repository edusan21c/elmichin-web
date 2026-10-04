# app/blueprints/admin/monitor.py
from datetime import datetime, timedelta
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from . import bp
from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.factura import Factura
from app.models.tienda import Tienda
from app.utils.decorators import admin_requerido


def hora_local():
    return datetime.utcnow() - timedelta(hours=5)


@bp.route('/monitor')
@login_required
@admin_requerido
def monitor():
    tiendas = Tienda.query.filter_by(activa=True).all() if current_user.es_programador() else []
    return render_template('admin/monitor.html', tiendas=tiendas)


@bp.route('/api/monitor')
@login_required
@admin_requerido
def api_monitor():
    ahora_utc = datetime.utcnow()
    ahora_local = hora_local()

    # Filtro por tienda
    tienda_filtro = request.args.get('tienda', type=int)
    if not current_user.es_programador():
        tienda_filtro = current_user.tienda_id

    # ============ 1. USUARIOS ACTIVOS (últimos 5 min) ============
    hace_5min = ahora_utc - timedelta(minutes=5)
    q_activos = db.session.query(
        AuditLog.username,
        AuditLog.user_nombre,
        func.max(AuditLog.fecha).label('ultima'),
    ).filter(
        AuditLog.fecha >= hace_5min,
        AuditLog.username.isnot(None),
        AuditLog.username != 'anonimo',
    ).group_by(AuditLog.username, AuditLog.user_nombre).all()

    usuarios_activos = []
    for u in q_activos:
        delta = (ahora_utc - u.ultima).total_seconds()
        if delta < 60:
            hace = f'hace {int(delta)}s'
        else:
            hace = f'hace {int(delta/60)}m'
        usuarios_activos.append({
            'username': u.username,
            'nombre': u.user_nombre or u.username,
            'hace': hace,
        })

    # ============ 2. FACTURAS ÚLTIMAS 2 HORAS ============
    hace_2h = ahora_utc - timedelta(hours=2)
    q_facturas = Factura.query.filter(Factura.fecha_hora >= hace_2h)
    if tienda_filtro:
        q_facturas = q_facturas.filter(Factura.tienda_id == tienda_filtro)
    facturas = q_facturas.order_by(Factura.fecha_hora.desc()).limit(20).all()

    facturas_data = [{
        'numero': f.numero_factura,
        'cliente': f.cliente.nombre if f.cliente else '',
        'total': float(f.total or 0),
        'metodo': f.metodo_pago or '',
        'hora': (f.fecha_hora - timedelta(hours=5)).strftime('%H:%M'),
        'es_remota': f.origen == 'remota_recibida',
        'precio_manual': bool(f.precio_manual),
    } for f in facturas]

    # ============ 3. EVENTOS RECIENTES (últimos 30) ============
    q_eventos = AuditLog.query.order_by(AuditLog.fecha.desc()).limit(30)
    if tienda_filtro:
        q_eventos = q_eventos.filter(
            or_(AuditLog.tienda_id == tienda_filtro, AuditLog.tienda_id.is_(None))
        )
    eventos = q_eventos.all()

    eventos_data = [{
        'id': e.id,
        'hora': (e.fecha - timedelta(hours=5)).strftime('%H:%M:%S'),
        'username': e.username or '—',
        'accion': e.accion,
        'detalle': e.detalle or '',
    } for e in eventos]

    # ============ 4. RESUMEN DEL DÍA ============
    inicio_hoy_utc = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=5)

    q_hoy = Factura.query.filter(Factura.fecha_hora >= inicio_hoy_utc)
    if tienda_filtro:
        q_hoy = q_hoy.filter(Factura.tienda_id == tienda_filtro)

    total_hoy = float(db.session.query(
        func.coalesce(func.sum(Factura.total), 0)
    ).filter(
        Factura.fecha_hora >= inicio_hoy_utc,
        Factura.tienda_id == tienda_filtro if tienda_filtro else True,
    ).scalar() or 0)

    num_fact_hoy = q_hoy.count()

    return jsonify({
        'ok': True,
        'hora_actual': ahora_local.strftime('%H:%M:%S'),
        'usuarios_activos': usuarios_activos,
        'facturas_recientes': facturas_data,
        'eventos': eventos_data,
        'resumen_dia': {
            'total_hoy': total_hoy,
            'num_facturas': num_fact_hoy,
        },
    })