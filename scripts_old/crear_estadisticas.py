# scripts/crear_estadisticas.py
# Modulo de Estadisticas con graficos Chart.js.
# Ejecutar UNA VEZ: python scripts\crear_estadisticas.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== BLUEPRINT ====================
ARCHIVOS['app/blueprints/estadisticas/__init__.py'] = '''# app/blueprints/estadisticas/__init__.py
from flask import Blueprint

bp = Blueprint('estadisticas', __name__, url_prefix='/estadisticas')

from . import routes  # noqa: E402, F401
'''

ARCHIVOS['app/blueprints/estadisticas/routes.py'] = '''# app/blueprints/estadisticas/routes.py
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
'''

# ==================== TEMPLATE ====================
ARCHIVOS['app/templates/estadisticas/index.html'] = '''{% extends 'base.html' %}
{% block titulo %}Estadísticas{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
    <h1 class="h3 mb-0">
        <i class="bi bi-bar-chart"></i> Estadísticas
        {% if current_user.es_programador() and tiendas|length > 1 %}
            <small class="text-muted">- Tienda:
                <select id="selector-tienda" class="form-select form-select-sm d-inline-block" style="width:auto;">
                    {% for t in tiendas %}
                        <option value="{{ t.id }}" {% if t.id == tienda_id %}selected{% endif %}>{{ t.nombre }}</option>
                    {% endfor %}
                </select>
            </small>
        {% endif %}
    </h1>
    <div class="btn-group">
        <a href="?periodo=7d{% if tienda_id %}&tienda={{ tienda_id }}{% endif %}"
           class="btn btn-sm {% if periodo == '7d' %}btn-primary{% else %}btn-outline-primary{% endif %}">7 días</a>
        <a href="?periodo=30d{% if tienda_id %}&tienda={{ tienda_id }}{% endif %}"
           class="btn btn-sm {% if periodo == '30d' %}btn-primary{% else %}btn-outline-primary{% endif %}">30 días</a>
        <a href="?periodo=mes{% if tienda_id %}&tienda={{ tienda_id }}{% endif %}"
           class="btn btn-sm {% if periodo == 'mes' %}btn-primary{% else %}btn-outline-primary{% endif %}">Este mes</a>
        <a href="?periodo=año{% if tienda_id %}&tienda={{ tienda_id }}{% endif %}"
           class="btn btn-sm {% if periodo == 'año' %}btn-primary{% else %}btn-outline-primary{% endif %}">Este año</a>
    </div>
</div>

<!-- KPIs -->
<div class="row g-3 mb-4" id="kpis-container">
    <div class="col-md-3">
        <div class="card border-primary">
            <div class="card-body">
                <div class="text-muted small">💰 Total vendido</div>
                <div class="fs-3 fw-bold text-primary" id="kpi-total">$0</div>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card border-info">
            <div class="card-body">
                <div class="text-muted small">🧾 Facturas</div>
                <div class="fs-3 fw-bold text-info" id="kpi-facturas">0</div>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card border-success">
            <div class="card-body">
                <div class="text-muted small">🎫 Ticket promedio</div>
                <div class="fs-3 fw-bold text-success" id="kpi-ticket">$0</div>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card border-warning">
            <div class="card-body">
                <div class="text-muted small">📦 Productos vendidos</div>
                <div class="fs-3 fw-bold text-warning" id="kpi-productos">0</div>
            </div>
        </div>
    </div>
</div>

<!-- Gráficos -->
<div class="row g-3">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header bg-white fw-semibold">
                📈 Ventas por día
            </div>
            <div class="card-body">
                <canvas id="chart-ventas-dia" height="100"></canvas>
            </div>
        </div>
    </div>
    <div class="col-lg-4">
        <div class="card">
            <div class="card-header bg-white fw-semibold">
                💳 Métodos de pago
            </div>
            <div class="card-body">
                <canvas id="chart-metodos"></canvas>
            </div>
        </div>
    </div>
    <div class="col-lg-6">
        <div class="card">
            <div class="card-header bg-white fw-semibold">
                🏆 Top 10 productos más vendidos
            </div>
            <div class="card-body">
                <canvas id="chart-top" height="200"></canvas>
            </div>
        </div>
    </div>
    <div class="col-lg-6">
        <div class="card">
            <div class="card-header bg-white fw-semibold">
                ⏰ Ventas por hora del día
            </div>
            <div class="card-body">
                <canvas id="chart-horas" height="200"></canvas>
            </div>
        </div>
    </div>
    {% if current_user.es_programador() %}
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-white fw-semibold">
                🏪 Comparativa entre tiendas
            </div>
            <div class="card-body">
                <canvas id="chart-comparativa" height="60"></canvas>
            </div>
        </div>
    </div>
    {% endif %}
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
    window.EST_CONFIG = {
        tiendaId: {{ tienda_id or 0 }},
        periodo: "{{ periodo }}",
        urlDatos: "{{ url_for('estadisticas.api_datos') }}",
    };
</script>
<script src="{{ url_for('static', filename='js/estadisticas.js') }}"></script>
{% endblock %}
'''

# ==================== JAVASCRIPT ====================
ARCHIVOS['app/static/js/estadisticas.js'] = '''// app/static/js/estadisticas.js
(function() {
    'use strict';

    const CFG = window.EST_CONFIG || {};

    function fmt(n) {
        return '$' + Math.round(n || 0).toLocaleString('es-CO');
    }

    async function cargarDatos() {
        try {
            const url = CFG.urlDatos + '?periodo=' + CFG.periodo + '&tienda=' + CFG.tiendaId;
            const r = await fetch(url);
            const data = await r.json();
            render(data);
        } catch (e) {
            console.error('Error cargando datos:', e);
        }
    }

    function render(data) {
        // KPIs
        document.getElementById('kpi-total').textContent = fmt(data.kpis.total_vendido);
        document.getElementById('kpi-facturas').textContent = data.kpis.num_facturas;
        document.getElementById('kpi-ticket').textContent = fmt(data.kpis.ticket_promedio);
        document.getElementById('kpi-productos').textContent = data.kpis.total_productos;

        // Chart: Ventas por día (línea)
        new Chart(document.getElementById('chart-ventas-dia'), {
            type: 'line',
            data: {
                labels: data.ventas_dia.labels,
                datasets: [{
                    label: 'Ventas ($)',
                    data: data.ventas_dia.datos,
                    borderColor: 'rgb(13, 110, 253)',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    fill: true,
                    tension: 0.3,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => fmt(c.parsed.y) } }
                },
                scales: {
                    y: { ticks: { callback: (v) => '$' + (v/1000).toFixed(0) + 'k' } }
                }
            }
        });

        // Chart: Métodos de pago (doughnut)
        new Chart(document.getElementById('chart-metodos'), {
            type: 'doughnut',
            data: {
                labels: data.metodos.labels,
                datasets: [{
                    data: data.metodos.datos,
                    backgroundColor: ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6c757d']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: { callbacks: { label: (c) => c.label + ': ' + fmt(c.parsed) } }
                }
            }
        });

        // Chart: Top productos (horizontal bar)
        new Chart(document.getElementById('chart-top'), {
            type: 'bar',
            data: {
                labels: data.top_productos.labels.map(l => l.length > 30 ? l.substring(0,30) + '...' : l),
                datasets: [{
                    label: 'Unidades vendidas',
                    data: data.top_productos.cantidades,
                    backgroundColor: 'rgb(25, 135, 84)',
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { x: { beginAtZero: true } }
            }
        });

        // Chart: Ventas por hora (bar)
        new Chart(document.getElementById('chart-horas'), {
            type: 'bar',
            data: {
                labels: data.por_hora.labels,
                datasets: [{
                    label: 'Ventas',
                    data: data.por_hora.datos,
                    backgroundColor: 'rgb(255, 193, 7)',
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => fmt(c.parsed.y) } }
                },
                scales: { y: { ticks: { callback: (v) => '$' + (v/1000).toFixed(0) + 'k' } } }
            }
        });

        // Chart: Comparativa (solo programador)
        const compCanvas = document.getElementById('chart-comparativa');
        if (compCanvas && data.comparativa && Object.keys(data.comparativa).length > 0) {
            new Chart(compCanvas, {
                type: 'bar',
                data: {
                    labels: Object.keys(data.comparativa),
                    datasets: [{
                        label: 'Ventas por tienda',
                        data: Object.values(data.comparativa),
                        backgroundColor: ['#0d6efd', '#198754'],
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { label: (c) => fmt(c.parsed.y) } }
                    }
                }
            });
        }
    }

    // Selector de tienda
    const st = document.getElementById('selector-tienda');
    if (st) {
        st.addEventListener('change', function() {
            const url = new URL(window.location.href);
            url.searchParams.set('tienda', this.value);
            window.location.href = url.toString();
        });
    }

    // Cargar
    cargarDatos();

})();
'''


def main():
    print(f'Creando modulo de Estadisticas en: {RAIZ}')
    print('-' * 60)
    for rel_path, contenido in ARCHIVOS.items():
        ruta = os.path.join(RAIZ, *rel_path.split('/'))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f'  OK  {rel_path}')
    print('-' * 60)
    print(f'Listo: {len(ARCHIVOS)} archivos creados.')


if __name__ == '__main__':
    main()