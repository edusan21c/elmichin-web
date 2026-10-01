# scripts/crear_reportes.py
# Modulo de Reportes: lista de facturas, detalle, cuentas por cobrar y abonos.
# Ejecutar UNA VEZ: python scripts\crear_reportes.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== BLUEPRINT ====================
ARCHIVOS['app/blueprints/reportes/__init__.py'] = '''# app/blueprints/reportes/__init__.py
from flask import Blueprint

bp = Blueprint('reportes', __name__, url_prefix='/reportes')

from . import routes  # noqa: E402, F401
'''

ARCHIVOS['app/blueprints/reportes/routes.py'] = '''# app/blueprints/reportes/routes.py
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from . import bp
from app.extensions import db
from app.models.tienda import Tienda
from app.models.cliente import Cliente
from app.models.factura import Factura, DetalleFactura
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


def redondear(v):
    return Decimal(str(v or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ==================== VENTAS ====================
@bp.route('/')
@bp.route('/ventas')
@login_required
def ventas():
    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()

    # Filtros
    desde_str = request.args.get('desde', '', type=str).strip()
    hasta_str = request.args.get('hasta', '', type=str).strip()
    q = request.args.get('q', '', type=str).strip()

    hoy = hora_local().date()
    if not desde_str:
        desde_str = hoy.strftime('%Y-%m-%d')
    if not hasta_str:
        hasta_str = hoy.strftime('%Y-%m-%d')

    try:
        desde = datetime.strptime(desde_str, '%Y-%m-%d')
        hasta = datetime.strptime(hasta_str, '%Y-%m-%d') + timedelta(days=1)
    except ValueError:
        desde = datetime.combine(hoy, datetime.min.time())
        hasta = desde + timedelta(days=1)

    # Query base
    query = Factura.query.filter(
        Factura.tienda_id == tienda_id,
        Factura.fecha_hora >= desde,
        Factura.fecha_hora < hasta
    )

    if q:
        # Buscar por numero de factura o cliente
        query = query.join(Cliente).filter(
            or_(
                Factura.numero_factura.ilike(f'%{q}%'),
                Cliente.nombre.ilike(f'%{q}%')
            )
        )

    facturas = query.order_by(Factura.fecha_hora.desc()).limit(500).all()

    # Totales del periodo
    total_periodo = db.session.query(func.coalesce(func.sum(Factura.total), 0)).filter(
        Factura.tienda_id == tienda_id,
        Factura.fecha_hora >= desde,
        Factura.fecha_hora < hasta
    ).scalar() or 0

    num_facturas = len(facturas)
    ticket_promedio = float(total_periodo) / num_facturas if num_facturas > 0 else 0

    return render_template(
        'reportes/ventas.html',
        facturas=facturas,
        tiendas=tiendas,
        tienda_id=tienda_id,
        desde=desde_str,
        hasta=hasta_str,
        q=q,
        total_periodo=float(total_periodo),
        num_facturas=num_facturas,
        ticket_promedio=ticket_promedio,
    )


# ==================== DETALLE DE FACTURA ====================
@bp.route('/<int:factura_id>')
@login_required
def detalle(factura_id):
    factura = Factura.query.get_or_404(factura_id)
    detalles = DetalleFactura.query.filter_by(factura_id=factura_id).all()
    pagos = Pago.query.filter_by(factura_id=factura_id).order_by(Pago.fecha.desc()).all()
    return render_template(
        'reportes/detalle.html',
        factura=factura,
        detalles=detalles,
        pagos=pagos,
        cliente=factura.cliente,
    )


# ==================== CUENTAS POR COBRAR ====================
@bp.route('/cuentas-por-cobrar')
@login_required
def cuentas_por_cobrar():
    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()

    # Clientes con deuda
    clientes_deuda = (Cliente.query
                      .filter(Cliente.tienda_id == tienda_id,
                              Cliente.saldo_actual > 0.01)
                      .order_by(Cliente.saldo_actual.desc())
                      .all())

    total_deuda = sum(float(c.saldo_actual or 0) for c in clientes_deuda)

    return render_template(
        'reportes/cuentas_por_cobrar.html',
        clientes=clientes_deuda,
        tiendas=tiendas,
        tienda_id=tienda_id,
        total_deuda=total_deuda,
    )


# ==================== API: FACTURAS PENDIENTES DE UN CLIENTE ====================
@bp.route('/api/cliente/<int:cliente_id>/pendientes')
@login_required
def api_facturas_pendientes(cliente_id):
    facturas = (Factura.query
                .filter_by(cliente_id=cliente_id)
                .filter(Factura.estado_credito == 'pendiente',
                        Factura.saldo_pendiente > 0.01)
                .order_by(Factura.fecha_hora.asc())
                .all())

    return jsonify([{
        'id': f.id,
        'numero': f.numero_factura,
        'fecha': (f.fecha_hora - timedelta(hours=5)).strftime('%d/%m/%Y'),
        'total': float(f.total or 0),
        'saldo': float(f.saldo_pendiente or 0),
    } for f in facturas])


# ==================== REGISTRAR ABONO ====================
@bp.route('/abono', methods=['POST'])
@login_required
def registrar_abono():
    factura_id = request.form.get('factura_id', type=int)
    monto = request.form.get('monto', type=float)
    metodo = request.form.get('metodo', 'efectivo', type=str)

    if not factura_id or not monto or monto <= 0:
        flash('Datos inválidos', 'danger')
        return redirect(url_for('reportes.cuentas_por_cobrar'))

    factura = Factura.query.get_or_404(factura_id)
    if factura.estado_credito != 'pendiente' or factura.saldo_pendiente <= 0:
        flash('Esta factura no tiene saldo pendiente', 'warning')
        return redirect(url_for('reportes.cuentas_por_cobrar'))

    saldo_actual = float(factura.saldo_pendiente)

    if monto > saldo_actual + 0.01:
        flash(f'El abono no puede superar el saldo (${saldo_actual:,.0f})', 'danger')
        return redirect(url_for('reportes.cuentas_por_cobrar'))

    # Redondear al saldo exacto si está muy cerca
    if abs(monto - saldo_actual) < 0.10:
        monto = saldo_actual

    nuevo_saldo = redondear(saldo_actual - monto)

    # Crear pago
    pago = Pago(
        factura_id=factura.id,
        tienda_id=factura.tienda_id,
        monto=Decimal(str(monto)),
        metodo_pago=metodo,
    )
    db.session.add(pago)

    # Actualizar factura
    factura.saldo_pendiente = nuevo_saldo
    if nuevo_saldo <= 0.01:
        factura.estado_credito = 'pagado'
        factura.saldo_pendiente = Decimal('0')

    # Actualizar cliente
    cliente = factura.cliente
    cliente.saldo_actual = redondear(Decimal(str(cliente.saldo_actual or 0)) - Decimal(str(monto)))

    db.session.commit()

    flash(f'Abono de ${monto:,.0f} registrado. Nuevo saldo: ${float(factura.saldo_pendiente):,.0f}', 'success')
    return redirect(url_for('reportes.detalle', factura_id=factura.id))
'''

# ==================== TEMPLATES ====================
ARCHIVOS['app/templates/reportes/ventas.html'] = '''{% extends 'base.html' %}
{% block titulo %}Reportes de Ventas{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-graph-up"></i> Reportes de Ventas
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
</div>

<!-- Filtros -->
<div class="card mb-3">
    <div class="card-body py-2">
        <form method="GET" class="row g-2 align-items-end">
            <div class="col-md-3">
                <label class="form-label small mb-0">Desde</label>
                <input type="date" name="desde" class="form-control" value="{{ desde }}">
            </div>
            <div class="col-md-3">
                <label class="form-label small mb-0">Hasta</label>
                <input type="date" name="hasta" class="form-control" value="{{ hasta }}">
            </div>
            <div class="col-md-4">
                <label class="form-label small mb-0">Buscar</label>
                <input type="text" name="q" class="form-control" 
                       placeholder="N° factura o nombre cliente..." value="{{ q }}">
            </div>
            <div class="col-md-2">
                <button type="submit" class="btn btn-primary w-100">
                    <i class="bi bi-search"></i> Filtrar
                </button>
            </div>
        </form>

        <div class="mt-2">
            <a href="{{ url_for('reportes.ventas') }}" class="btn btn-sm btn-outline-secondary">
                <i class="bi bi-calendar-today"></i> Hoy
            </a>
            <a href="{{ url_for('reportes.ventas', desde=(hoy - timedelta(days=7)).strftime('%Y-%m-%d') if hoy else '', hasta=hoy.strftime('%Y-%m-%d') if hoy else '') }}" 
               class="btn btn-sm btn-outline-secondary">
                <i class="bi bi-calendar-week"></i> Últimos 7 días
            </a>
            <a href="{{ url_for('reportes.ventas', desde=(hoy - timedelta(days=30)).strftime('%Y-%m-%d') if hoy else '', hasta=hoy.strftime('%Y-%m-%d') if hoy else '') }}" 
               class="btn btn-sm btn-outline-secondary">
                <i class="bi bi-calendar-month"></i> Últimos 30 días
            </a>
        </div>
    </div>
</div>

<!-- KPIs -->
<div class="row g-3 mb-3">
    <div class="col-md-4">
        <div class="card border-primary">
            <div class="card-body">
                <div class="text-muted small">💰 Total vendido</div>
                <div class="fs-3 fw-bold text-primary">${{ "{:,.0f}".format(total_periodo) }}</div>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card border-info">
            <div class="card-body">
                <div class="text-muted small">🧾 Facturas</div>
                <div class="fs-3 fw-bold text-info">{{ num_facturas }}</div>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card border-success">
            <div class="card-body">
                <div class="text-muted small">🎫 Ticket promedio</div>
                <div class="fs-3 fw-bold text-success">${{ "{:,.0f}".format(ticket_promedio) }}</div>
            </div>
        </div>
    </div>
</div>

<!-- Tabla de facturas -->
<div class="card">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th>N° Factura</th>
                    <th>Fecha</th>
                    <th>Cliente</th>
                    <th class="text-end">Total</th>
                    <th class="text-center">Método</th>
                    <th class="text-center">Estado</th>
                    <th class="text-end">Acciones</th>
                </tr>
            </thead>
            <tbody>
                {% for f in facturas %}
                <tr>
                    <td class="fw-semibold">{{ f.numero_factura }}</td>
                    <td class="text-muted small">{{ f.fecha_hora | fecha_local }}</td>
                    <td>{{ f.cliente.nombre }}</td>
                    <td class="text-end fw-semibold">${{ "{:,.0f}".format(f.total) }}</td>
                    <td class="text-center">
                        <span class="badge bg-secondary">{{ f.metodo_pago }}</span>
                    </td>
                    <td class="text-center">
                        {% if f.estado_credito == 'pendiente' %}
                            <span class="badge bg-warning text-dark">Pendiente</span>
                        {% else %}
                            <span class="badge bg-success">Pagado</span>
                        {% endif %}
                    </td>
                    <td class="text-end">
                        <a href="{{ url_for('reportes.detalle', factura_id=f.id) }}" 
                           class="btn btn-sm btn-outline-primary">
                            <i class="bi bi-eye"></i> Ver
                        </a>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="7" class="text-center py-5 text-muted">
                        <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                        No hay facturas en este período.
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<script>
const st = document.getElementById('selector-tienda');
if (st) {
    st.addEventListener('change', function() {
        const url = new URL(window.location.href);
        url.searchParams.set('tienda', this.value);
        window.location.href = url.toString();
    });
}
</script>
{% endblock %}
'''

ARCHIVOS['app/templates/reportes/detalle.html'] = '''{% extends 'base.html' %}
{% block titulo %}Factura {{ factura.numero_factura }}{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-receipt"></i> Factura {{ factura.numero_factura }}
    </h1>
    <div>
        <a href="{{ url_for('reportes.ventas') }}" class="btn btn-outline-secondary">
            <i class="bi bi-arrow-left"></i> Volver
        </a>
        <a href="{{ url_for('facturacion.ticket', factura_id=factura.id) }}" class="btn btn-primary">
            <i class="bi bi-printer"></i> Ver ticket
        </a>
    </div>
</div>

<div class="row g-3">
    <div class="col-lg-8">
        <div class="card mb-3">
            <div class="card-header bg-white fw-semibold">
                <i class="bi bi-person-circle"></i> Cliente
            </div>
            <div class="card-body">
                <p class="mb-1"><strong>{{ cliente.nombre }}</strong></p>
                {% if cliente.documento %}<p class="mb-1 text-muted small">Doc: {{ cliente.documento }}</p>{% endif %}
                {% if cliente.telefono %}<p class="mb-1 text-muted small">Tel: {{ cliente.telefono }}</p>{% endif %}
                {% if cliente.saldo_actual and cliente.saldo_actual > 0 %}
                <div class="alert alert-warning mt-2 mb-0 small">
                    <i class="bi bi-exclamation-triangle"></i>
                    Saldo total del cliente: <strong>${{ "{:,.0f}".format(cliente.saldo_actual) }}</strong>
                </div>
                {% endif %}
            </div>
        </div>

        <div class="card mb-3">
            <div class="card-header bg-white fw-semibold">
                <i class="bi bi-cart3"></i> Productos
            </div>
            <div class="table-responsive">
                <table class="table mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>Producto</th>
                            <th class="text-center">Cant</th>
                            <th class="text-end">P. Unit</th>
                            <th class="text-end">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for d in detalles %}
                        <tr>
                            <td>{{ d.producto_nombre }}</td>
                            <td class="text-center">{{ d.cantidad }}</td>
                            <td class="text-end">${{ "{:,.0f}".format(d.precio_unitario) }}</td>
                            <td class="text-end">${{ "{:,.0f}".format(d.subtotal) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                    <tfoot>
                        <tr><th colspan="3" class="text-end">Subtotal</th><th class="text-end">${{ "{:,.0f}".format(factura.subtotal) }}</th></tr>
                        {% if factura.recargo_nequi > 0 %}
                        <tr><td colspan="3" class="text-end">Recargo digital</td><td class="text-end">${{ "{:,.0f}".format(factura.recargo_nequi) }}</td></tr>
                        {% endif %}
                        {% if factura.recargo_bolsa > 0 %}
                        <tr><td colspan="3" class="text-end">Bolsas</td><td class="text-end">${{ "{:,.0f}".format(factura.recargo_bolsa) }}</td></tr>
                        {% endif %}
                        <tr class="table-success"><th colspan="3" class="text-end">TOTAL</th><th class="text-end">${{ "{:,.0f}".format(factura.total) }}</th></tr>
                    </tfoot>
                </table>
            </div>
        </div>
    </div>

    <div class="col-lg-4">
        <div class="card mb-3">
            <div class="card-header bg-white fw-semibold">
                <i class="bi bi-info-circle"></i> Info
            </div>
            <div class="card-body">
                <p class="mb-1 small"><strong>Fecha:</strong> {{ factura.fecha_hora | fecha_local }}</p>
                <p class="mb-1 small"><strong>Método:</strong> {{ factura.metodo_pago | upper }}</p>
                <p class="mb-1 small"><strong>Estado:</strong> 
                    {% if factura.estado_credito == 'pendiente' %}
                        <span class="badge bg-warning text-dark">Pendiente</span>
                    {% else %}
                        <span class="badge bg-success">Pagado</span>
                    {% endif %}
                </p>
                {% if factura.usuario %}
                <p class="mb-1 small"><strong>Atendido por:</strong> {{ factura.usuario.nombre }}</p>
                {% endif %}
            </div>
        </div>

        {% if factura.estado_credito == 'pendiente' %}
        <div class="card border-warning mb-3">
            <div class="card-header bg-warning text-dark fw-semibold">
                <i class="bi bi-cash"></i> Saldo pendiente
            </div>
            <div class="card-body">
                <div class="fs-3 fw-bold text-danger mb-3">${{ "{:,.0f}".format(factura.saldo_pendiente) }}</div>
                <form method="POST" action="{{ url_for('reportes.registrar_abono') }}">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                    <input type="hidden" name="factura_id" value="{{ factura.id }}">
                    <div class="mb-2">
                        <label class="form-label small">Monto a abonar</label>
                        <div class="input-group">
                            <span class="input-group-text">$</span>
                            <input type="number" name="monto" class="form-control" 
                                   max="{{ factura.saldo_pendiente }}" min="1" required>
                        </div>
                    </div>
                    <div class="mb-2">
                        <label class="form-label small">Método</label>
                        <select name="metodo" class="form-select form-select-sm">
                            <option value="efectivo">Efectivo</option>
                            <option value="nequi">Nequi</option>
                            <option value="daviplata">Daviplata</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-warning w-100">
                        <i class="bi bi-check-circle"></i> Registrar abono
                    </button>
                </form>
            </div>
        </div>
        {% endif %}

        {% if pagos %}
        <div class="card">
            <div class="card-header bg-white fw-semibold">
                <i class="bi bi-clock-history"></i> Historial de pagos
            </div>
            <div class="card-body p-0">
                <table class="table table-sm mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>Fecha</th>
                            <th class="text-end">Monto</th>
                            <th>Método</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in pagos %}
                        <tr>
                            <td class="small">{{ p.fecha | fecha_local }}</td>
                            <td class="text-end small">${{ "{:,.0f}".format(p.monto) }}</td>
                            <td class="small">{{ p.metodo_pago }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
'''

ARCHIVOS['app/templates/reportes/cuentas_por_cobrar.html'] = '''{% extends 'base.html' %}
{% block titulo %}Cuentas por Cobrar{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-cash-coin"></i> Cuentas por Cobrar
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
    <div class="fs-4 text-danger">
        Deuda total: <strong>${{ "{:,.0f}".format(total_deuda) }}</strong>
    </div>
</div>

{% if not clientes %}
<div class="alert alert-success">
    <i class="bi bi-check-circle"></i>
    ¡Excelente! No hay clientes con deuda pendiente.
</div>
{% else %}
<div class="card">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th>Cliente</th>
                    <th>Documento</th>
                    <th>Teléfono</th>
                    <th class="text-end">Saldo</th>
                    <th class="text-end">Acciones</th>
                </tr>
            </thead>
            <tbody>
                {% for c in clientes %}
                <tr>
                    <td class="fw-semibold">{{ c.nombre }}</td>
                    <td class="text-muted small">{{ c.documento or '-' }}</td>
                    <td class="text-muted small">{{ c.telefono or '-' }}</td>
                    <td class="text-end fw-bold text-danger">${{ "{:,.0f}".format(c.saldo_actual) }}</td>
                    <td class="text-end">
                        <button type="button" class="btn btn-sm btn-primary btn-ver"
                                data-id="{{ c.id }}" data-nombre="{{ c.nombre }}"
                                data-bs-toggle="modal" data-bs-target="#modalFacturas">
                            <i class="bi bi-list-ul"></i> Ver facturas
                        </button>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endif %}

<!-- Modal facturas -->
<div class="modal fade" id="modalFacturas" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Facturas de <span id="modal-cliente-nombre"></span></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body" id="modal-body">
                <div class="text-center py-3">
                    <div class="spinner-border"></div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
const st = document.getElementById('selector-tienda');
if (st) {
    st.addEventListener('change', function() {
        const url = new URL(window.location.href);
        url.searchParams.set('tienda', this.value);
        window.location.href = url.toString();
    });
}

document.querySelectorAll('.btn-ver').forEach(btn => {
    btn.addEventListener('click', async function() {
        const id = this.dataset.id;
        const nombre = this.dataset.nombre;
        document.getElementById('modal-cliente-nombre').textContent = nombre;
        const body = document.getElementById('modal-body');
        body.innerHTML = '<div class="text-center py-3"><div class="spinner-border"></div></div>';

        try {
            const r = await fetch('/reportes/api/cliente/' + id + '/pendientes');
            const data = await r.json();
            if (!data.length) {
                body.innerHTML = '<p class="text-muted">No hay facturas pendientes</p>';
                return;
            }
            let html = '<table class="table table-sm"><thead class="table-light"><tr>' +
                       '<th>Factura</th><th>Fecha</th><th class="text-end">Total</th>' +
                       '<th class="text-end">Saldo</th><th></th></tr></thead><tbody>';
            data.forEach(f => {
                html += `<tr>
                    <td class="fw-semibold">${f.numero}</td>
                    <td>${f.fecha}</td>
                    <td class="text-end">$${f.total.toLocaleString('es-CO')}</td>
                    <td class="text-end text-danger">$${f.saldo.toLocaleString('es-CO')}</td>
                    <td class="text-end">
                        <a href="/reportes/${f.id}" class="btn btn-sm btn-outline-primary">Ver</a>
                    </td>
                </tr>`;
            });
            html += '</tbody></table>';
            body.innerHTML = html;
        } catch (e) {
            body.innerHTML = '<div class="alert alert-danger">Error cargando facturas</p>';
        }
    });
});
</script>
{% endblock %}
'''


def main():
    print(f'Creando modulo de reportes en: {RAIZ}')
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