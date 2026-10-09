# app/blueprints/caja/routes.py
"""Modulo Caja — control de medios de pago.
Totales por método (efectivo/nequi/daviplata/crédito) con filtros
Día/Semana/Mes/Año. Lee de tabla pagos para desglosar mixtos.
"""
from datetime import datetime, timedelta
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.tienda import Tienda
from app.models.factura import Factura
from app.models.pago import Pago


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
    """Devuelve (desde_utc, hasta_utc, etiqueta)."""
    hoy = hora_local()

    if periodo == 'dia':
        inicio_local = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
        etiqueta = 'Hoy ' + hoy.strftime('%d/%m/%Y')
    elif periodo == 'semana':
        inicio_local = (hoy - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        etiqueta = 'Últimos 7 días'
    elif periodo == 'mes':
        inicio_local = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        etiqueta = hoy.strftime('%B %Y').capitalize()
    elif periodo == 'año':
        inicio_local = hoy.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        etiqueta = 'Año ' + str(hoy.year)
    else:
        inicio_local = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
        etiqueta = 'Hoy'

    fin_local = hoy.replace(hour=23, minute=59, second=59, microsecond=0)

    return inicio_local + timedelta(hours=5), fin_local + timedelta(hours=5), etiqueta


# ==================== PANTALLA ====================
@bp.route('/')
@login_required
def index():
    if not current_user.es_admin() and not current_user.es_programador():
        return 'No autorizado', 403

    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()
    periodo = request.args.get('periodo', 'dia')

    return render_template(
        'caja/index.html',
        tienda_id=tienda_id,
        tiendas=tiendas,
        periodo=periodo,
    )


# ==================== API ====================
@bp.route('/api/datos')
@login_required
def api_datos():
    if not current_user.es_admin() and not current_user.es_programador():
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403

    tienda_id = tienda_actual()
    periodo = request.args.get('periodo', 'dia')
    desde_utc, hasta_utc, etiqueta = calcular_rango(periodo)

    # Facturas del período
    q = Factura.query.filter(
        Factura.fecha_hora >= desde_utc,
        Factura.fecha_hora <= hasta_utc,
    )
    if tienda_id:
        q = q.filter(Factura.tienda_id == tienda_id)
    facturas = q.all()
    ids_facturas = [f.id for f in facturas]

    # ============ COBROS POR MÉTODO (tabla pagos) ============
    metodos = {'efectivo': 0.0, 'nequi': 0.0, 'daviplata': 0.0, 'otro': 0.0}
    facturas_por_metodo = {'efectivo': 0, 'nequi': 0, 'daviplata': 0, 'credito': 0, 'otro': 0}

    pagos = []
    if ids_facturas:
        pagos = Pago.query.filter(Pago.factura_id.in_(ids_facturas)).all()
        for p in pagos:
            m = (p.metodo_pago or 'otro').lower()
            if m not in metodos:
                m = 'otro'
            metodos[m] += float(p.monto or 0)

    # ============ CRÉDITO OTORGADO/COBRADO/PENDIENTE ============
    credito_otorgado = 0.0
    credito_cobrado = 0.0
    for f in facturas:
        if (f.tipo_pago or '').lower() == 'credito':
            total_f = float(f.total or 0)
            saldo_f = float(f.saldo_pendiente or 0)
            credito_otorgado += total_f
            credito_cobrado += (total_f - saldo_f)

    # ============ CANTIDAD DE FACTURAS POR MÉTODO ============
    for f in facturas:
        m = (f.metodo_pago or 'otro').lower()
        if m == 'mixto':
            pagos_f = [p for p in pagos if p.factura_id == f.id]
            m = (pagos_f[0].metodo_pago or 'otro').lower() if pagos_f else 'otro'
        if m not in facturas_por_metodo:
            m = 'otro'
        facturas_por_metodo[m] += 1

    total_vendido = sum(float(f.total or 0) for f in facturas)
    total_cobrado = metodos['efectivo'] + metodos['nequi'] + metodos['daviplata'] + metodos['otro']

    return jsonify({
        'ok': True,
        'periodo': periodo,
        'etiqueta': etiqueta,
        'tienda_id': tienda_id,
        'totales': {
            'efectivo': metodos['efectivo'],
            'nequi': metodos['nequi'],
            'daviplata': metodos['daviplata'],
            'credito': credito_otorgado,
            'otro': metodos['otro'],
            'total_cobrado': total_cobrado,
            'total_vendido': total_vendido,
        },
        'facturas': {
            'efectivo': facturas_por_metodo['efectivo'],
            'nequi': facturas_por_metodo['nequi'],
            'daviplata': facturas_por_metodo['daviplata'],
            'credito': facturas_por_metodo['credito'],
            'otro': facturas_por_metodo['otro'],
            'total': len(facturas),
        },
        'credito_detalle': {
            'otorgado': credito_otorgado,
            'cobrado': credito_cobrado,
            'pendiente': credito_otorgado - credito_cobrado,
        },
    })