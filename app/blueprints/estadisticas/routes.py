# app/blueprints/estadisticas/routes.py
from datetime import datetime, timedelta
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from . import bp
from app.extensions import db
from app.models.tienda import Tienda
from app.models.factura import Factura, DetalleFactura


def hora_local():
    return datetime.utcnow() - timedelta(hours=5)


def tienda_actual():
    if current_user.es_programador():
        tid = request.args.get('tienda', type=int)
        if tid:
            return tid
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None
    return current_user.tienda_id


def calcular_rango(periodo):
    """Devuelve (desde_utc, hasta_utc) según el periodo."""
    hoy_local = hora_local().replace(hour=23, minute=59, second=59, microsecond=0)

    if periodo == '7d':
        inicio_local = (hora_local() - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == '30d':
        inicio_local = (hora_local() - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == 'mes':
        inicio_local = hora_local().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif periodo == 'año':
        inicio_local = hora_local().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # todo
        return None, None

    # Convertir a UTC (sumar 5h)
    desde_utc = inicio_local + timedelta(hours=5)
    hasta_utc = hoy_local + timedelta(hours=5)
    return desde_utc, hasta_utc


# ==================== PANTALLA PRINCIPAL ====================
@bp.route('/')
@login_required
def index():
    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()
    periodo = request.args.get('periodo', '30d')

    return render_template(
        'estadisticas/index.html',
        tienda_id=tienda_id,
        tiendas=tiendas,
        periodo=periodo,
    )


# ==================== API: DATOS DE GRAFICOS ====================
@bp.route('/api/datos')
@login_required
def api_datos():
    tienda_id = tienda_actual()
    periodo = request.args.get('periodo', '30d')
    desde, hasta = calcular_rango(periodo)

    # Query base
    q = Factura.query
    if tienda_id:
        q = q.filter(Factura.tienda_id == tienda_id)
    if desde and hasta:
        q = q.filter(Factura.fecha_hora >= desde, Factura.fecha_hora < hasta)

    facturas = q.all()

    # KPIs
    total_vendido = float(sum(f.total or 0 for f in facturas))
    num_facturas = len(facturas)
    ticket_promedio = total_vendido / num_facturas if num_facturas > 0 else 0
    total_productos = sum(
        d.cantidad for f in facturas
        for d in f.detalles
    )

    # Ventas por día
    ventas_dia = {}
    for f in facturas:
        fecha_local = f.fecha_hora - timedelta(hours=5)
        dia = fecha_local.strftime('%Y-%m-%d')
        ventas_dia[dia] = ventas_dia.get(dia, 0) + float(f.total or 0)

    # Top 10 productos
    productos_q = (
        db.session.query(
            DetalleFactura.producto_nombre,
            func.sum(DetalleFactura.cantidad).label('cantidad'),
            func.sum(DetalleFactura.subtotal).label('ingresos'),
        )
        .join(Factura, Factura.id == DetalleFactura.factura_id)
        .filter(Factura.id.in_([f.id for f in facturas]) if facturas else False)
        .group_by(DetalleFactura.producto_nombre)
        .order_by(func.sum(DetalleFactura.cantidad).desc())
        .limit(10)
        .all()
    )

    # Métodos de pago
    metodos = {}
    for f in facturas:
        m = f.metodo_pago or 'otro'
        metodos[m] = metodos.get(m, 0) + float(f.total or 0)

    # Ventas por hora
    por_hora = {str(h): 0 for h in range(24)}
    for f in facturas:
        hora_local = (f.fecha_hora - timedelta(hours=5)).hour
        por_hora[str(hora_local)] = por_hora.get(str(hora_local), 0) + float(f.total or 0)

    # Comparativa entre tiendas (solo programador)
    comparativa = {}
    if current_user.es_programador():
        for t in Tienda.query.filter_by(activa=True).all():
            q_t = Factura.query.filter(Factura.tienda_id == t.id)
            if desde and hasta:
                q_t = q_t.filter(Factura.fecha_hora >= desde, Factura.fecha_hora < hasta)
            total_t = float(db.session.query(func.coalesce(func.sum(Factura.total), 0)).filter(
                Factura.tienda_id == t.id,
                Factura.fecha_hora >= desde if desde else True,
                Factura.fecha_hora < hasta if hasta else True,
            ).scalar() or 0)
            comparativa[t.nombre] = total_t

    return jsonify({
        'kpis': {
            'total_vendido': total_vendido,
            'num_facturas': num_facturas,
            'ticket_promedio': ticket_promedio,
            'total_productos': total_productos,
        },
        'ventas_dia': {
            'labels': sorted(ventas_dia.keys()),
            'datos': [ventas_dia[d] for d in sorted(ventas_dia.keys())],
        },
        'top_productos': {
            'labels': [p[0] for p in productos_q],
            'cantidades': [int(p[1]) for p in productos_q],
            'ingresos': [float(p[2]) for p in productos_q],
        },
        'metodos': {
            'labels': list(metodos.keys()),
            'datos': list(metodos.values()),
        },
        'por_hora': {
            'labels': [f'{h}h' for h in range(24)],
            'datos': [por_hora[str(h)] for h in range(24)],
        },
        'comparativa': comparativa,
    })
