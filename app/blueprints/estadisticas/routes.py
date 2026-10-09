# app/blueprints/estadisticas/routes.py
from datetime import datetime, timedelta
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from . import bp
from app.extensions import db
from app.models.tienda import Tienda
from app.models.factura import Factura, DetalleFactura
from app.models.producto import Producto, ProductoTienda


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

    # v2.38-fix-metodos: ventas por método de pago (desglosa mixtos)
    # Cada factura cuenta su propio método. Si es mixta, se desglosa
    # por los pagos individuales (efectivo/nequi/daviplata).
    # Suma de métodos = Total vendido (cuadra con KPI)
    metodos = {}
    for f in facturas:
        m = (f.metodo_pago or 'otro').lower()
        if m == 'mixto':
            # Desglosar por pagos individuales
            for p in f.pagos.all():
                mp = (p.metodo_pago or 'otro').lower()
                metodos[mp] = metodos.get(mp, 0) + float(p.monto or 0)
        else:
            metodos[m] = metodos.get(m, 0) + float(f.total or 0)

    # v2.38: estado del crédito en el período
    # Otorgado: suma de facturas con tipo_pago='credito'
    # Cobrado:  lo que ya se pagó de esas facturas (total - saldo_pendiente)
    # Pendiente: suma de saldo_pendiente actual de esas facturas
    credito_otorgado = 0.0
    credito_cobrado = 0.0
    credito_pendiente = 0.0
    for f in facturas:
        if (f.tipo_pago or '').lower() == 'credito':
            total_f = float(f.total or 0)
            saldo_f = float(f.saldo_pendiente or 0)
            credito_otorgado += total_f
            credito_pendiente += saldo_f
            credito_cobrado += (total_f - saldo_f)

    # Ventas por hora
    por_hora = {str(h): 0 for h in range(24)}
    for f in facturas:
        hora_local_f = (f.fecha_hora - timedelta(hours=5)).hour
        por_hora[str(hora_local_f)] = por_hora.get(str(hora_local_f), 0) + float(f.total or 0)

    # Comparativa entre tiendas (solo programador)
    comparativa = {}
    if current_user.es_programador():
        for t in Tienda.query.filter_by(activa=True).all():
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
        'credito': {
            'otorgado': credito_otorgado,
            'cobrado': credito_cobrado,
            'pendiente': credito_pendiente,
        },
        'por_hora': {
            'labels': [f'{h}h' for h in range(24)],
            'datos': [por_hora[str(h)] for h in range(24)],
        },
        'comparativa': comparativa,
    })


# ==================== ANÁLISIS AVANZADO ====================
@bp.route('/analisis')
@login_required
def analisis():
    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()
    return render_template(
        'estadisticas/analisis.html',
        tienda_id=tienda_id,
        tiendas=tiendas,
    )


@bp.route('/api/analisis')
@login_required
def api_analisis():
    """Devuelve todos los análisis avanzados en una sola llamada."""
    from app.models.cliente import Cliente

    tienda_id = tienda_actual()
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'Sin tienda'}), 400

    hoy_local = hora_local()  # UTC-5

    # ============ 1. PRODUCTOS POR AGOTARSE ============
    productos_agotar = (db.session.query(
            Producto.id,
            Producto.nombre,
            Producto.codigo_barras,
            ProductoTienda.cantidad,
            ProductoTienda.precio_venta,
        )
        .join(ProductoTienda, ProductoTienda.producto_id == Producto.id)
        .filter(
            ProductoTienda.tienda_id == tienda_id,
            ProductoTienda.cantidad > 0,
            ProductoTienda.cantidad <= 5,
        )
        .order_by(ProductoTienda.cantidad.asc())
        .limit(20)
        .all()
    )

    agotar_data = [{
        'id': r.id,
        'nombre': r.nombre,
        'codigo': r.codigo_barras or '',
        'stock': int(r.cantidad),
        'precio': float(r.precio_venta or 0),
    } for r in productos_agotar]

    # Productos agotados (cantidad = 0)
    agotados_count = (ProductoTienda.query
        .filter(ProductoTienda.tienda_id == tienda_id)
        .filter(ProductoTienda.cantidad <= 0)
        .count())

    # ============ 2. COMPARATIVA MES ACTUAL VS ANTERIOR ============
    inicio_mes_actual_local = hoy_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if inicio_mes_actual_local.month == 1:
        inicio_mes_ant_local = inicio_mes_actual_local.replace(year=inicio_mes_actual_local.year - 1, month=12)
    else:
        inicio_mes_ant_local = inicio_mes_actual_local.replace(month=inicio_mes_actual_local.month - 1)
    fin_mes_ant_local = inicio_mes_actual_local

    desde_actual_utc = inicio_mes_actual_local + timedelta(hours=5)
    hasta_actual_utc = hoy_local + timedelta(hours=5)

    desde_ant_utc = inicio_mes_ant_local + timedelta(hours=5)
    hasta_ant_utc = fin_mes_ant_local + timedelta(hours=5)

    total_mes_actual = float(db.session.query(
        func.coalesce(func.sum(Factura.total), 0)
    ).filter(
        Factura.tienda_id == tienda_id,
        Factura.fecha_hora >= desde_actual_utc,
        Factura.fecha_hora < hasta_actual_utc,
    ).scalar() or 0)

    total_mes_anterior = float(db.session.query(
        func.coalesce(func.sum(Factura.total), 0)
    ).filter(
        Factura.tienda_id == tienda_id,
        Factura.fecha_hora >= desde_ant_utc,
        Factura.fecha_hora < hasta_ant_utc,
    ).scalar() or 0)

    num_fact_actual = Factura.query.filter(
        Factura.tienda_id == tienda_id,
        Factura.fecha_hora >= desde_actual_utc,
        Factura.fecha_hora < hasta_actual_utc,
    ).count()

    num_fact_anterior = Factura.query.filter(
        Factura.tienda_id == tienda_id,
        Factura.fecha_hora >= desde_ant_utc,
        Factura.fecha_hora < hasta_ant_utc,
    ).count()

    if total_mes_anterior > 0:
        variacion_pct = ((total_mes_actual - total_mes_anterior) / total_mes_anterior) * 100
    else:
        variacion_pct = 0

    # ============ 3. VENTAS POR DÍA DE LA SEMANA ============
    desde_90d_local = hoy_local - timedelta(days=90)
    desde_90d_utc = desde_90d_local + timedelta(hours=5)

    facturas_90d = Factura.query.filter(
        Factura.tienda_id == tienda_id,
        Factura.fecha_hora >= desde_90d_utc,
    ).all()

    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    ventas_por_dia = {d: 0 for d in dias_semana}
    for f in facturas_90d:
        fecha_local = f.fecha_hora - timedelta(hours=5)
        dia = dias_semana[fecha_local.weekday()]
        ventas_por_dia[dia] += float(f.total or 0)

    # ============ 4. TOP 10 PRODUCTOS POR GANANCIA ============
    desde_90d_query = db.session.query(
            DetalleFactura.producto_id,
            DetalleFactura.producto_nombre,
            func.sum(DetalleFactura.cantidad).label('cantidad_vendida'),
            func.sum(DetalleFactura.subtotal).label('total_vendido'),
        ).join(
            Factura, Factura.id == DetalleFactura.factura_id
        ).filter(
            Factura.tienda_id == tienda_id,
            Factura.fecha_hora >= desde_90d_utc,
        ).group_by(
            DetalleFactura.producto_id,
            DetalleFactura.producto_nombre,
        ).order_by(
            func.sum(DetalleFactura.subtotal).desc()
        ).limit(30).all()

    top_ganancia = []
    for r in desde_90d_query:
        pres = ProductoTienda.query.filter_by(
            producto_id=r.producto_id, tienda_id=tienda_id
        ).first()
        if not pres:
            continue
        precio_prov = float(pres.precio_proveedor or 0)
        cant = int(r.cantidad_vendida)
        total_vend = float(r.total_vendido)
        ganancia = total_vend - (precio_prov * cant)
        top_ganancia.append({
            'nombre': r.producto_nombre,
            'cantidad': cant,
            'total_vendido': total_vend,
            'ganancia': ganancia,
        })

    top_ganancia.sort(key=lambda x: x['ganancia'], reverse=True)
    top_ganancia = top_ganancia[:10]

    # ============ 5. VALOR DEL INVENTARIO ============
    inventario_query = (db.session.query(
            func.count(ProductoTienda.producto_id).label('total_items'),
            func.coalesce(func.sum(ProductoTienda.cantidad), 0).label('unidades'),
            func.coalesce(func.sum(ProductoTienda.cantidad * ProductoTienda.precio_proveedor), 0).label('valor_costo'),
            func.coalesce(func.sum(ProductoTienda.cantidad * ProductoTienda.precio_venta), 0).label('valor_venta'),
        )
        .filter(ProductoTienda.tienda_id == tienda_id)
        .first()
    )

    return jsonify({
        'ok': True,
        'agotar': {
            'productos': agotar_data,
            'total_agotados': agotados_count,
            'total_bajos': len(agotar_data),
        },
        'comparativa': {
            'mes_actual': total_mes_actual,
            'mes_anterior': total_mes_anterior,
            'variacion_pct': variacion_pct,
            'fact_actual': num_fact_actual,
            'fact_anterior': num_fact_anterior,
        },
        'por_dia_semana': ventas_por_dia,
        'top_ganancia': top_ganancia,
        'inventario': {
            'total_items': int(inventario_query.total_items or 0),
            'unidades': int(inventario_query.unidades or 0),
            'valor_costo': float(inventario_query.valor_costo or 0),
            'valor_venta': float(inventario_query.valor_venta or 0),
            'ganancia_potencial': float((inventario_query.valor_venta or 0) - (inventario_query.valor_costo or 0)),
        },
    })