# app/blueprints/bi/routes.py
"""BI — Business Intelligence.
Panel de tendencias anuales y análisis ejecutivo."""
from datetime import datetime, timedelta
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from . import bp
from app.extensions import db
from app.models.tienda import Tienda
from app.models.factura import Factura, DetalleFactura
from app.models.producto import Producto


MESES_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


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


def anio_actual():
    return hora_local().year


def anios_disponibles(tienda_id):
    q = db.session.query(
        func.extract('year', Factura.fecha_hora).label('anio')
    )
    if tienda_id:
        q = q.filter(Factura.tienda_id == tienda_id)
    anios = sorted({int(r.anio) for r in q.distinct().all() if r.anio}, reverse=True)
    if not anios:
        anios = [anio_actual()]
    return anios


# ==================== PANTALLA PRINCIPAL ====================
@bp.route('/')
@login_required
def index():
    if not current_user.es_admin() and not current_user.es_programador():
        return 'No autorizado', 403

    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()
    anios = anios_disponibles(tienda_id)
    anio = request.args.get('anio', type=int) or anios[0]
    mes = request.args.get('mes', type=int) or hora_local().month

    return render_template(
        'bi/index.html',
        tienda_id=tienda_id,
        tiendas=tiendas,
        anios=anios,
        anio=anio,
        mes=mes,
        meses=MESES_ES,
    )


# ==================== API: DATOS ====================
@bp.route('/api/datos')
@login_required
def api_datos():
    if not current_user.es_admin() and not current_user.es_programador():
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403

    tienda_id = tienda_actual()
    anio = request.args.get('anio', type=int) or anio_actual()
    mes = request.args.get('mes', type=int) or hora_local().month
    if mes < 1 or mes > 12:
        mes = hora_local().month

    # Rango del año seleccionado
    desde_utc = datetime(anio, 1, 1, 0, 0, 0) + timedelta(hours=5)
    hasta_utc = datetime(anio + 1, 1, 1, 0, 0, 0) + timedelta(hours=5)

    q = Factura.query.filter(
        Factura.fecha_hora >= desde_utc,
        Factura.fecha_hora < hasta_utc,
    )
    if tienda_id:
        q = q.filter(Factura.tienda_id == tienda_id)

    facturas = q.all()

    # ============ VENTAS POR MES (12 buckets) ============
    ventas_mes = [0.0] * 12
    facturas_mes = [0] * 12
    for f in facturas:
        fecha_local = f.fecha_hora - timedelta(hours=5)
        m = fecha_local.month - 1
        ventas_mes[m] += float(f.total or 0)
        facturas_mes[m] += 1

    total_anual = sum(ventas_mes)
    meses_con_ventas = [(i, v) for i, v in enumerate(ventas_mes) if v > 0]

    if meses_con_ventas:
        idx_mejor, val_mejor = max(meses_con_ventas, key=lambda x: x[1])
        idx_peor, val_peor = min(meses_con_ventas, key=lambda x: x[1])
        mejor_mes = {'nombre': MESES_ES[idx_mejor], 'valor': val_mejor}
        peor_mes = {'nombre': MESES_ES[idx_peor], 'valor': val_peor}
        promedio_mensual = total_anual / len(meses_con_ventas)
    else:
        mejor_mes = {'nombre': '-', 'valor': 0}
        peor_mes = {'nombre': '-', 'valor': 0}
        promedio_mensual = 0

    # ============ ESTADÍSTICAS DESCRIPTIVAS ============
    ventas_dia = {}
    facturas_dia = {}
    for f in facturas:
        fecha_local = f.fecha_hora - timedelta(hours=5)
        dia = fecha_local.strftime('%Y-%m-%d')
        ventas_dia[dia] = ventas_dia.get(dia, 0) + float(f.total or 0)
        facturas_dia[dia] = facturas_dia.get(dia, 0) + 1

    serie_dias = list(ventas_dia.values())
    serie_facturas = list(facturas_dia.values())

    n = len(serie_dias)
    if n > 0:
        media = sum(serie_dias) / n
        serie_ordenada = sorted(serie_dias)
        if n % 2 == 1:
            mediana = serie_ordenada[n // 2]
        else:
            mediana = (serie_ordenada[n // 2 - 1] + serie_ordenada[n // 2]) / 2
        varianza = sum((x - media) ** 2 for x in serie_dias) / n
        desviacion = varianza ** 0.5
    else:
        media = mediana = varianza = desviacion = 0

    if serie_facturas:
        freq = {}
        for x in serie_facturas:
            freq[x] = freq.get(x, 0) + 1
        moda = max(freq.items(), key=lambda x: x[1])
        moda_valor = moda[0]
        moda_repeticiones = moda[1]
    else:
        moda_valor = 0
        moda_repeticiones = 0

    # ============ FASE 2: DETALLE DEL MES ============
    facturas_mes_sel = []
    for f in facturas:
        fecha_local = f.fecha_hora - timedelta(hours=5)
        if fecha_local.month == mes:
            facturas_mes_sel.append(f)

    # --- Top 5 productos del mes ---
    productos_mes = {}
    for f in facturas_mes_sel:
        for d in f.detalles:
            nombre = d.producto_nombre or '?'
            if nombre not in productos_mes:
                productos_mes[nombre] = {'cantidad': 0, 'ingresos': 0.0}
            productos_mes[nombre]['cantidad'] += int(d.cantidad or 0)
            productos_mes[nombre]['ingresos'] += float(d.subtotal or 0)

    top_productos = sorted(
        [{'nombre': k, **v} for k, v in productos_mes.items()],
        key=lambda x: x['cantidad'],
        reverse=True
    )[:20]

    # --- Top 5 clientes del mes ---
    clientes_mes = {}
    for f in facturas_mes_sel:
        cid = f.cliente_id or 0
        if cid not in clientes_mes:
            clientes_mes[cid] = {'nombre': f.cliente.nombre if f.cliente else '?', 'total': 0.0, 'facturas': 0}
        clientes_mes[cid]['total'] += float(f.total or 0)
        clientes_mes[cid]['facturas'] += 1

    top_clientes = sorted(
        [{'id': k, **v} for k, v in clientes_mes.items()],
        key=lambda x: x['total'],
        reverse=True
    )[:20]

    # --- Ventas rápidas vs normales ---
    ventas_rapidas = {'total': 0.0, 'facturas': 0}
    ventas_normales = {'total': 0.0, 'facturas': 0}
    for f in facturas_mes_sel:
        nombre_cli = (f.cliente.nombre if f.cliente else '') or ''
        if nombre_cli.lower().startswith('venta r'):
            ventas_rapidas['total'] += float(f.total or 0)
            ventas_rapidas['facturas'] += 1
        else:
            ventas_normales['total'] += float(f.total or 0)
            ventas_normales['facturas'] += 1

    # --- Ventas por categoría del mes ---
    categorias_mes = {}
    for f in facturas_mes_sel:
        for d in f.detalles:
            prod = db.session.get(Producto, d.producto_id) if d.producto_id else None
            cat = (prod.categoria if prod and prod.categoria else 'Sin categoría')
            if cat not in categorias_mes:
                categorias_mes[cat] = 0.0
            categorias_mes[cat] += float(d.subtotal or 0)

    categorias_ordenadas = sorted(
        [{'nombre': k, 'total': v} for k, v in categorias_mes.items()],
        key=lambda x: x['total'],
        reverse=True
    )

    # --- Total facturas del mes ---
    total_fact_mes = len(facturas_mes_sel)
    total_vendido_mes = sum(float(f.total or 0) for f in facturas_mes_sel)
    ticket_prom_mes = total_vendido_mes / total_fact_mes if total_fact_mes > 0 else 0

    anios = anios_disponibles(tienda_id)

    return jsonify({
        'ok': True,
        'anio': anio,
        'mes': mes,
        'tienda_id': tienda_id,
        'anios_disponibles': anios,
        'kpis': {
            'total_anual': total_anual,
            'mejor_mes': mejor_mes,
            'peor_mes': peor_mes,
            'promedio_mensual': promedio_mensual,
            'total_facturas': len(facturas),
        },
        'meses': {
            'labels': MESES_ES,
            'datos': ventas_mes,
            'facturas': facturas_mes,
        },
        'estadisticas': {
            'media': media,
            'mediana': mediana,
            'moda': moda_valor,
            'moda_repeticiones': moda_repeticiones,
            'varianza': varianza,
            'desviacion': desviacion,
            'dias_con_ventas': n,
        },
        # Fase 2
        'mes_actual': {
            'numero': mes,
            'nombre': MESES_ES[mes - 1],
            'total_vendido': total_vendido_mes,
            'total_facturas': total_fact_mes,
            'ticket_promedio': ticket_prom_mes,
        },
        'top_productos': top_productos,
        'top_clientes': top_clientes,
        'ventas_rapidas': ventas_rapidas,
        'ventas_normales': ventas_normales,
        'categorias': categorias_ordenadas,
    })