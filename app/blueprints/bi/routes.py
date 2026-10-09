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
from app.models.factura import Factura


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
    """Devuelve los años con facturas ordenados desc."""
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

    return render_template(
        'bi/index.html',
        tienda_id=tienda_id,
        tiendas=tiendas,
        anios=anios,
        anio=anio,
    )


# ==================== API: DATOS ====================
@bp.route('/api/datos')
@login_required
def api_datos():
    if not current_user.es_admin() and not current_user.es_programador():
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403

    tienda_id = tienda_actual()
    anio = request.args.get('anio', type=int) or anio_actual()

    # Rango del año seleccionado (en hora local UTC-5)
    desde_local = datetime(anio, 1, 1, 0, 0, 0)
    hasta_local = datetime(anio + 1, 1, 1, 0, 0, 0)
    desde_utc = desde_local + timedelta(hours=5)
    hasta_utc = hasta_local + timedelta(hours=5)

    # Query base
    q = Factura.query.filter(
        Factura.fecha_hora >= desde_utc,
        Factura.fecha_hora < hasta_utc,
    )
    if tienda_id:
        q = q.filter(Factura.tienda_id == tienda_id)

    facturas = q.all()

    # Ventas por mes (12 buckets)
    ventas_mes = [0.0] * 12
    facturas_mes = [0] * 12
    for f in facturas:
        fecha_local = f.fecha_hora - timedelta(hours=5)
        m = fecha_local.month - 1
        ventas_mes[m] += float(f.total or 0)
        facturas_mes[m] += 1

    # KPIs del año
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
    # Serie de ventas diarias del año (todas las que tuvieron ventas)
    ventas_dia = {}
    facturas_dia = {}
    for f in facturas:
        fecha_local = f.fecha_hora - timedelta(hours=5)
        dia = fecha_local.strftime('%Y-%m-%d')
        ventas_dia[dia] = ventas_dia.get(dia, 0) + float(f.total or 0)
        facturas_dia[dia] = facturas_dia.get(dia, 0) + 1

    serie_dias = list(ventas_dia.values())
    serie_facturas = list(facturas_dia.values())

    # Media, mediana, varianza, desviación (sobre ventas diarias)
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

    # Moda: cantidad de facturas por día (la que más se repite)
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

    # Datos disponibles para dropdown
    anios = anios_disponibles(tienda_id)

    return jsonify({
        'ok': True,
        'anio': anio,
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
    })