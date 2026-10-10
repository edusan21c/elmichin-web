# app/blueprints/caja/routes.py
"""Modulo Caja — control de medios de pago.
Ventas por método (contable, suma = total vendido) + categorías + clientes por método."""
from datetime import datetime, timedelta
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.tienda import Tienda
from app.models.factura import Factura, DetalleFactura
from app.models.pago import Pago
from app.models.producto import Producto
from sqlalchemy import or_


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

    q = Factura.query.filter(
        Factura.fecha_hora >= desde_utc,
        Factura.fecha_hora <= hasta_utc,
    )
    if tienda_id:
        q = q.filter(Factura.tienda_id == tienda_id)
    facturas = q.all()
    ids_facturas = [f.id for f in facturas]

    pagos = []
    if ids_facturas:
        pagos = Pago.query.filter(Pago.factura_id.in_(ids_facturas)).all()

    pagos_por_factura = {}
    for p in pagos:
        pagos_por_factura.setdefault(p.factura_id, []).append(p)

    ventas_metodo = {'efectivo': 0.0, 'nequi': 0.0, 'daviplata': 0.0, 'credito': 0.0, 'otro': 0.0}
    facturas_por_metodo = {'efectivo': 0, 'nequi': 0, 'daviplata': 0, 'credito': 0, 'otro': 0}

    credito_otorgado = 0.0
    credito_cobrado = 0.0

    for f in facturas:
        total_f = float(f.total or 0)
        tipo = (f.tipo_pago or '').lower()
        metodo_f = (f.metodo_pago or 'otro').lower()

        if tipo == 'credito':
            ventas_metodo['credito'] += total_f
            facturas_por_metodo['credito'] += 1
            saldo_f = float(f.saldo_pendiente or 0)
            credito_otorgado += total_f
            credito_cobrado += (total_f - saldo_f)
        elif metodo_f == 'mixto':
            pagos_f = pagos_por_factura.get(f.id, [])
            if pagos_f:
                for p in pagos_f:
                    pm = (p.metodo_pago or 'otro').lower()
                    if pm not in ventas_metodo:
                        pm = 'otro'
                    ventas_metodo[pm] += float(p.monto or 0)
                facturas_por_metodo['otro'] += 1
            else:
                ventas_metodo['otro'] += total_f
                facturas_por_metodo['otro'] += 1
        elif metodo_f in ('efectivo', 'nequi', 'daviplata'):
            ventas_metodo[metodo_f] += total_f
            facturas_por_metodo[metodo_f] += 1
        else:
            ventas_metodo['otro'] += total_f
            facturas_por_metodo['otro'] += 1

    cobros_metodo = {'efectivo': 0.0, 'nequi': 0.0, 'daviplata': 0.0, 'otro': 0.0}
    for p in pagos:
        pm = (p.metodo_pago or 'otro').lower()
        if pm not in cobros_metodo:
            pm = 'otro'
        cobros_metodo[pm] += float(p.monto or 0)

    total_vendido = sum(float(f.total or 0) for f in facturas)
    total_cobrado = sum(cobros_metodo.values())

    categorias = {}
    for f in facturas:
        for d in f.detalles:
            prod = db.session.get(Producto, d.producto_id) if d.producto_id else None
            cat = (prod.categoria if prod and prod.categoria else 'Sin categoría').strip()
            if cat not in categorias:
                categorias[cat] = {'ingresos': 0.0, 'unidades': 0, 'productos_distintos': set()}
            categorias[cat]['ingresos'] += float(d.subtotal or 0)
            categorias[cat]['unidades'] += int(d.cantidad or 0)
            categorias[cat]['productos_distintos'].add(d.producto_nombre or '?')

    categorias_lista = sorted(
        [{'nombre': k, 'ingresos': v['ingresos'], 'unidades': v['unidades'],
          'productos_distintos': len(v['productos_distintos'])}
         for k, v in categorias.items()],
        key=lambda x: x['ingresos'],
        reverse=True
    )

    clientes_por_metodo = {
        'efectivo': {}, 'nequi': {}, 'daviplata': {}, 'credito': {},
    }

    for f in facturas:
        cid = f.cliente_id or 0
        if cid == 0:
            continue
        nombre = f.cliente.nombre if f.cliente else '?'
        total_f = float(f.total or 0)

        if (f.tipo_pago or '').lower() == 'credito':
            m = 'credito'
        else:
            m = (f.metodo_pago or 'otro').lower()
            if m == 'mixto':
                pagos_f = pagos_por_factura.get(f.id, [])
                if pagos_f:
                    por_m = {}
                    for p in pagos_f:
                        pm = (p.metodo_pago or 'otro').lower()
                        por_m[pm] = por_m.get(pm, 0) + float(p.monto or 0)
                    m = max(por_m.items(), key=lambda x: x[1])[0] if por_m else 'otro'

        if m not in clientes_por_metodo:
            m = 'efectivo'

        if cid not in clientes_por_metodo[m]:
            clientes_por_metodo[m][cid] = {'nombre': nombre, 'total': 0.0, 'facturas': 0}
        clientes_por_metodo[m][cid]['total'] += total_f
        clientes_por_metodo[m][cid]['facturas'] += 1

    def top_clientes_metodo(dic, limite=10):
        return sorted(
            [{'id': k, **v} for k, v in dic.items()],
            key=lambda x: x['total'],
            reverse=True
        )[:limite]

    return jsonify({
        'ok': True,
        'periodo': periodo,
        'etiqueta': etiqueta,
        'tienda_id': tienda_id,
        'totales': {
            'efectivo': ventas_metodo['efectivo'],
            'nequi': ventas_metodo['nequi'],
            'daviplata': ventas_metodo['daviplata'],
            'credito': ventas_metodo['credito'],
            'otro': ventas_metodo['otro'],
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
        'categorias': categorias_lista,
        'clientes_por_metodo': {
            'efectivo': top_clientes_metodo(clientes_por_metodo['efectivo']),
            'nequi': top_clientes_metodo(clientes_por_metodo['nequi']),
            'daviplata': top_clientes_metodo(clientes_por_metodo['daviplata']),
            'credito': top_clientes_metodo(clientes_por_metodo['credito']),
        },
    })


# ==================== API: PRODUCTOS DE UNA CATEGORÍA (drill-down) ====================
@bp.route('/api/categoria-productos')
@login_required
def api_categoria_productos():
    if not current_user.es_admin() and not current_user.es_programador():
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403

    categoria = request.args.get('categoria', '', type=str).strip()
    if not categoria:
        return jsonify({'ok': False, 'error': 'Sin categoría'}), 400

    tienda_id = tienda_actual()
    periodo = request.args.get('periodo', 'dia')
    desde_utc, hasta_utc, etiqueta = calcular_rango(periodo)

    q = Factura.query.filter(
        Factura.fecha_hora >= desde_utc,
        Factura.fecha_hora <= hasta_utc,
    )
    if tienda_id:
        q = q.filter(Factura.tienda_id == tienda_id)
    facturas = q.all()

    productos = {}
    for f in facturas:
        for d in f.detalles:
            prod = db.session.get(Producto, d.producto_id) if d.producto_id else None
            cat = (prod.categoria if prod and prod.categoria else 'Sin categoría').strip()
            if cat != categoria:
                continue
            nombre = d.producto_nombre or '?'
            if nombre not in productos:
                productos[nombre] = {'unidades': 0, 'ingresos': 0.0}
            productos[nombre]['unidades'] += int(d.cantidad or 0)
            productos[nombre]['ingresos'] += float(d.subtotal or 0)

    lista = sorted(
        [{'nombre': k, **v} for k, v in productos.items()],
        key=lambda x: x['ingresos'],
        reverse=True
    )

    total_unidades = sum(p['unidades'] for p in lista)
    total_ingresos = sum(p['ingresos'] for p in lista)

    return jsonify({
        'ok': True,
        'categoria': categoria,
        'etiqueta': etiqueta,
        'productos': lista,
        'total_unidades': total_unidades,
        'total_ingresos': total_ingresos,
    })


# ==================== API: BUSCAR PRODUCTOS (buscador en vivo, v2.59/v2.60) ====================
@bp.route('/api/buscar-productos')
@login_required
def api_buscar_productos():
    if not current_user.es_admin() and not current_user.es_programador():
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403

    q = request.args.get('q', '', type=str).strip()
    if len(q) < 2:
        return jsonify({'ok': True, 'productos': [], 'etiqueta': ''})

    tienda_id = tienda_actual()
    periodo = request.args.get('periodo', 'dia')
    desde_utc, hasta_utc, etiqueta = calcular_rango(periodo)

    patron = f'%{q}%'
    q_lower = q.lower()

    # v2.60: número → barcode primero. Letra → nombre primero.
    empieza_con_numero = q[0].isdigit() if q else False

    if empieza_con_numero:
        productos = (Producto.query
                     .filter(Producto.codigo_barras.ilike(patron))
                     .order_by(Producto.nombre)
                     .limit(20)
                     .all())
        if not productos:
            productos = (Producto.query
                         .filter(Producto.nombre.ilike(patron))
                         .order_by(Producto.nombre)
                         .limit(20)
                         .all())
    else:
        productos_por_nombre = (Producto.query
                                .filter(Producto.nombre.ilike(patron))
                                .limit(50)
                                .all())
        if productos_por_nombre:
            def prioridad(prod):
                nombre_lower = (prod.nombre or '').lower()
                if nombre_lower.startswith(q_lower):
                    return (1, nombre_lower)
                for palabra in nombre_lower.split():
                    if palabra.startswith(q_lower):
                        return (2, nombre_lower)
                return (3, nombre_lower)
            productos = sorted(productos_por_nombre, key=prioridad)[:20]
        else:
            productos = (Producto.query
                         .filter(Producto.codigo_barras.ilike(patron))
                         .order_by(Producto.nombre)
                         .limit(20)
                         .all())

    if not productos:
        return jsonify({'ok': True, 'productos': [], 'etiqueta': etiqueta})

    qf = Factura.query.filter(
        Factura.fecha_hora >= desde_utc,
        Factura.fecha_hora <= hasta_utc,
    )
    if tienda_id:
        qf = qf.filter(Factura.tienda_id == tienda_id)
    facturas = qf.all()

    ventas_por_nombre = {}
    for f in facturas:
        for d in f.detalles:
            nombre = d.producto_nombre or '?'
            if nombre not in ventas_por_nombre:
                ventas_por_nombre[nombre] = {'unidades': 0, 'ingresos': 0.0}
            ventas_por_nombre[nombre]['unidades'] += int(d.cantidad or 0)
            ventas_por_nombre[nombre]['ingresos'] += float(d.subtotal or 0)

    resultado = []
    for p in productos:
        v = ventas_por_nombre.get(p.nombre, {'unidades': 0, 'ingresos': 0.0})
        resultado.append({
            'id': p.id,
            'nombre': p.nombre,
            'codigo_barras': p.codigo_barras or '',
            'categoria': p.categoria or '',
            'unidades': v['unidades'],
            'ingresos': v['ingresos'],
        })

    return jsonify({
        'ok': True,
        'etiqueta': etiqueta,
        'productos': resultado,
    })