# scripts/crear_facturacion.py
# Crea el modulo de facturacion (blueprint + forms + routes + service + templates + JS).
# Ejecutar UNA VEZ: python scripts\crear_facturacion.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== SERVICES ====================
ARCHIVOS['app/services/__init__.py'] = ''

ARCHIVOS['app/services/facturacion_service.py'] = '''# app/services/facturacion_service.py
"""Logica de negocio para facturacion."""
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.cliente import Cliente
from app.models.factura import Factura, DetalleFactura
from app.models.venta import Venta


def redondear(v):
    return Decimal(str(v or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def generar_numero_factura(tienda_id):
    """Genera un numero de factura unico para la tienda. Formato: FAC-T{tienda}-0001."""
    ultima = (Factura.query
              .filter_by(tienda_id=tienda_id)
              .order_by(Factura.id.desc())
              .first())
    if ultima:
        try:
            num = int(ultima.numero_factura.split('-')[-1])
            siguiente = num + 1
        except (ValueError, IndexError):
            siguiente = 1
    else:
        siguiente = 1
    return f'FAC-T{tienda_id}-{siguiente:04d}'


def obtener_o_crear_cliente(tienda_id, nombre, documento='', direccion='', telefono='', email=''):
    """Busca un cliente por nombre+documento en la tienda, o lo crea."""
    nombre = (nombre or '').strip()
    documento = (documento or '').strip()

    query = Cliente.query.filter_by(tienda_id=tienda_id, nombre=nombre)
    if documento:
        query = query.filter_by(documento=documento)
    cliente = query.first()

    if cliente:
        # Actualizar datos si vienen nuevos
        if direccion and direccion != cliente.direccion:
            cliente.direccion = direccion
        if telefono and telefono != cliente.telefono:
            cliente.telefono = telefono
        if email and email != cliente.email:
            cliente.email = email
        return cliente

    cliente = Cliente(
        tienda_id=tienda_id,
        nombre=nombre,
        documento=documento or None,
        direccion=direccion or None,
        telefono=telefono or None,
        email=email or None,
        saldo_actual=Decimal('0'),
    )
    db.session.add(cliente)
    db.session.flush()
    return cliente


def crear_factura_completa(
    tienda_id,
    usuario_id,
    cliente_data,
    carrito,
    metodo_pago,
    recargo_porcentaje=Decimal('0.4'),
    bolsas_cantidad=0,
    valor_bolsa=Decimal('100'),
    valor_pagado=Decimal('0'),
):
    """
    Crea una factura completa:
    - Verifica stock
    - Crea/actualiza cliente
    - Calcula totales
    - Crea Factura + DetalleFactura
    - Registra ventas
    - Actualiza stock
    - Maneja credito
    Retorna (factura_id, error_mensaje).
    """
    if not carrito:
        return None, 'El carrito esta vacio'

    # ---------- 1. Verificar stock ----------
    items_procesados = []
    subtotal = Decimal('0')

    for item in carrito:
        producto_id = int(item['producto_id'])
        cantidad = int(item['cantidad'])
        if cantidad <= 0:
            return None, f'Cantidad invalida para el producto {producto_id}'

        producto = Producto.query.get(producto_id)
        if not producto:
            return None, f'Producto {producto_id} no encontrado'

        pres = ProductoTienda.query.filter_by(
            producto_id=producto_id, tienda_id=tienda_id
        ).first()
        if not pres:
            return None, f'Producto "{producto.nombre}" no tiene presentacion en esta tienda'

        if pres.cantidad < cantidad:
            return None, f'Stock insuficiente para "{producto.nombre}" (disponible: {pres.cantidad})'

        # Precio final: usar el que venga del carrito, o calcular
        precio_unitario = redondear(item.get('precio_unitario') or pres.calcular_precio(cantidad))
        item_subtotal = redondear(precio_unitario * cantidad)
        subtotal += item_subtotal

        items_procesados.append({
            'producto': producto,
            'presentacion': pres,
            'cantidad': cantidad,
            'precio_unitario': precio_unitario,
            'subtotal': item_subtotal,
        })

    # ---------- 2. Calcular totales ----------
    recargo = Decimal('0')
    if metodo_pago in ('nequi', 'daviplata'):
        recargo = redondear(subtotal * (Decimal(str(recargo_porcentaje)) / Decimal('100')))

    total_bolsas = redondear(Decimal(str(bolsas_cantidad)) * Decimal(str(valor_bolsa)))
    total_final = redondear(subtotal + recargo + total_bolsas)

    # ---------- 3. Manejar pago ----------
    if metodo_pago == 'credito':
        valor_pagado = Decimal('0')
        vueltas = Decimal('0')
        saldo_pendiente = total_final
    else:
        valor_pagado = redondear(valor_pagado)
        if valor_pagado < total_final - Decimal('0.01'):
            return None, f'Faltan ${total_final - valor_pagado:.0f} para completar el pago'
        vueltas = redondear(valor_pagado - total_final)
        saldo_pendiente = Decimal('0')

    # ---------- 4. Cliente ----------
    cliente = obtener_o_crear_cliente(
        tienda_id,
        cliente_data.get('nombre', 'Cliente ocasional'),
        cliente_data.get('documento', ''),
        cliente_data.get('direccion', ''),
        cliente_data.get('telefono', ''),
        cliente_data.get('email', ''),
    )

    # ---------- 5. Crear factura ----------
    numero = generar_numero_factura(tienda_id)
    tipo_pago = 'credito' if saldo_pendiente > 0 else 'contado'
    estado_credito = 'pendiente' if saldo_pendiente > 0 else 'pagado'

    factura = Factura(
        numero_factura=numero,
        tienda_id=tienda_id,
        cliente_id=cliente.id,
        usuario_id=usuario_id,
        subtotal=subtotal,
        total=total_final,
        metodo_pago=metodo_pago,
        recargo_nequi=recargo,
        recargo_bolsa=total_bolsas,
        valor_pagado=valor_pagado,
        vueltas=vueltas,
        tipo_pago=tipo_pago,
        estado_credito=estado_credito,
        saldo_pendiente=saldo_pendiente,
    )
    db.session.add(factura)
    db.session.flush()

    # ---------- 6. Detalle + ventas + stock ----------
    for item in items_procesados:
        detalle = DetalleFactura(
            factura_id=factura.id,
            producto_id=item['producto'].id,
            producto_nombre=item['producto'].nombre,
            cantidad=item['cantidad'],
            precio_unitario=item['precio_unitario'],
            subtotal=item['subtotal'],
        )
        db.session.add(detalle)

        venta = Venta(
            tienda_id=tienda_id,
            producto_id=item['producto'].id,
            cantidad=item['cantidad'],
            precio_unitario=item['precio_unitario'],
            total=item['subtotal'],
        )
        db.session.add(venta)

        item['presentacion'].cantidad = item['presentacion'].cantidad - item['cantidad']

    # ---------- 7. Si es credito, sumar al saldo del cliente ----------
    if saldo_pendiente > 0:
        cliente.saldo_actual = redondear(Decimal(str(cliente.saldo_actual or 0)) + saldo_pendiente)

    db.session.commit()
    return factura.id, None
'''

# ==================== BLUEPRINT ====================
ARCHIVOS['app/blueprints/facturacion/__init__.py'] = '''# app/blueprints/facturacion/__init__.py
from flask import Blueprint

bp = Blueprint('facturacion', __name__, url_prefix='/facturacion')

from . import routes  # noqa: E402, F401
'''

ARCHIVOS['app/blueprints/facturacion/routes.py'] = '''# app/blueprints/facturacion/routes.py
from decimal import Decimal
from flask import (
    render_template, request, jsonify, redirect, url_for,
    flash, current_app
)
from flask_login import login_required, current_user
from sqlalchemy import or_
from . import bp
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.tienda import Tienda
from app.models.factura import Factura, DetalleFactura
from app.services.facturacion_service import (
    crear_factura_completa, obtener_o_crear_cliente
)


def tienda_actual():
    if current_user.es_programador():
        tid = request.args.get('tienda', type=int)
        if tid:
            return tid
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None
    return current_user.tienda_id


# ==================== PANTALLA PRINCIPAL ====================
@bp.route('/')
@login_required
def nueva():
    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()
    recargo = current_app.config.get('RECARGO_NEQUI', 0.4)

    return render_template(
        'facturacion/nueva.html',
        tienda_id=tienda_id,
        tiendas=tiendas,
        recargo_porcentaje=recargo,
        valor_bolsa=100,
    )


# ==================== API: BUSCAR PRODUCTOS ====================
@bp.route('/api/productos')
@login_required
def api_productos():
    q = request.args.get('q', '', type=str).strip()
    if len(q) < 2:
        return jsonify([])

    tienda_id = tienda_actual()
    if not tienda_id:
        return jsonify([])

    productos = (Producto.query
                 .filter(or_(
                     Producto.nombre.ilike(f'%{q}%'),
                     Producto.codigo_barras.ilike(f'%{q}%')
                 ))
                 .order_by(Producto.nombre)
                 .limit(20)
                 .all())

    resultados = []
    for p in productos:
        pres = ProductoTienda.query.filter_by(
            producto_id=p.id, tienda_id=tienda_id
        ).first()
        if not pres:
            continue

        # Incluir precios por cantidad
        resultados.append({
            'id': p.id,
            'nombre': p.nombre,
            'codigo': p.codigo_barras or '',
            'categoria': p.categoria or '',
            'stock': pres.cantidad,
            'precio': float(pres.precio_venta or 0),
            'condicion1': pres.condicion1 or '',
            'precio1': float(pres.precio_venta1 or 0),
            'condicion2': pres.condicion2 or '',
            'precio2': float(pres.precio_venta2 or 0),
            'condicion3': pres.condicion3 or '',
            'precio3': float(pres.precio_venta3 or 0),
        })

    return jsonify(resultados)


# ==================== API: BUSCAR CLIENTES ====================
@bp.route('/api/clientes')
@login_required
def api_clientes():
    q = request.args.get('q', '', type=str).strip()
    if len(q) < 2:
        return jsonify([])

    tienda_id = tienda_actual()
    if not tienda_id:
        return jsonify([])

    clientes = (Cliente.query
                .filter_by(tienda_id=tienda_id)
                .filter(Cliente.nombre.ilike(f'%{q}%'))
                .limit(10)
                .all())

    return jsonify([{
        'id': c.id,
        'nombre': c.nombre,
        'documento': c.documento or '',
        'telefono': c.telefono or '',
        'direccion': c.direccion or '',
        'saldo': float(c.saldo_actual or 0),
    } for c in clientes])


# ==================== CREAR FACTURA ====================
@bp.route('/crear', methods=['POST'])
@login_required
def crear():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'error': 'Datos invalidos'}), 400

    tienda_id = tienda_actual()
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'No hay tienda activa'}), 400

    try:
        factura_id, error = crear_factura_completa(
            tienda_id=tienda_id,
            usuario_id=current_user.id,
            cliente_data=data.get('cliente', {}),
            carrito=data.get('carrito', []),
            metodo_pago=data.get('metodo_pago', 'efectivo'),
            recargo_porcentaje=Decimal(str(data.get('recargo_porcentaje', 0.4))),
            bolsas_cantidad=int(data.get('bolsas', 0)),
            valor_bolsa=Decimal('100'),
            valor_pagado=Decimal(str(data.get('valor_pagado', 0))),
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': f'Error del servidor: {str(e)}'}), 500

    if error:
        return jsonify({'ok': False, 'error': error}), 400

    return jsonify({
        'ok': True,
        'factura_id': factura_id,
        'redirect': url_for('facturacion.ticket', factura_id=factura_id),
    })


# ==================== VER TICKET ====================
@bp.route('/<int:factura_id>/ticket')
@login_required
def ticket(factura_id):
    factura = Factura.query.get_or_404(factura_id)
    detalles = DetalleFactura.query.filter_by(factura_id=factura_id).all()
    return render_template(
        'facturacion/ticket.html',
        factura=factura,
        detalles=detalles,
        cliente=factura.cliente,
    )


# ==================== API: CLIENTE POR NOMBRE EXACTO ====================
@bp.route('/api/cliente-exacto')
@login_required
def api_cliente_exacto():
    """Devuelve cliente por nombre exacto (para autocompletar)."""
    nombre = request.args.get('nombre', '', type=str).strip()
    if not nombre:
        return jsonify(None)
    tienda_id = tienda_actual()
    c = Cliente.query.filter_by(tienda_id=tienda_id, nombre=nombre).first()
    if c:
        return jsonify({
            'id': c.id,
            'nombre': c.nombre,
            'documento': c.documento or '',
            'telefono': c.telefono or '',
            'direccion': c.direccion or '',
            'saldo': float(c.saldo_actual or 0),
        })
    return jsonify(None)
'''

# Importar Cliente para que la ruta funcione
ARCHIVOS['app/blueprints/facturacion/_fix.py'] = '''# (archivo auxiliar - no se usa)'''

# ==================== TEMPLATES ====================
ARCHIVOS['app/templates/facturacion/nueva.html'] = '''{% extends 'base.html' %}
{% block titulo %}Nueva Factura{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-3">
    <h1 class="h3 mb-0">
        <i class="bi bi-receipt"></i> Nueva Factura
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

<div class="row g-3">
    <!-- ============ COLUMNA IZQUIERDA: BUSQUEDA ============ -->
    <div class="col-lg-5">
        <div class="card mb-3">
            <div class="card-body">
                <label class="form-label fw-semibold">
                    <i class="bi bi-search"></i> Buscar producto
                </label>
                <div class="input-group input-group-lg">
                    <span class="input-group-text"><i class="bi bi-upc-scan"></i></span>
                    <input type="text" id="input-buscar" class="form-control"
                           placeholder="Nombre o código de barras..."
                           autocomplete="off" autofocus>
                </div>
                <div id="resultados" class="list-group mt-2" style="max-height: 400px; overflow-y: auto;"></div>
            </div>
        </div>

        <!-- Carrito -->
        <div class="card">
            <div class="card-header bg-primary text-white">
                <i class="bi bi-cart3"></i> Carrito
                <span id="carrito-count" class="badge bg-light text-dark ms-2">0</span>
            </div>
            <div class="card-body p-0">
                <div id="carrito-vacio" class="text-center text-muted py-4">
                    <i class="bi bi-cart-x fs-1 d-block mb-2"></i>
                    Agrega productos para comenzar
                </div>
                <table class="table table-sm mb-0 d-none" id="carrito-tabla">
                    <thead class="table-light">
                        <tr>
                            <th>Producto</th>
                            <th class="text-center" style="width: 90px;">Cant.</th>
                            <th class="text-end" style="width: 90px;">P. Unit</th>
                            <th class="text-end" style="width: 90px;">Subtotal</th>
                            <th style="width: 40px;"></th>
                        </tr>
                    </thead>
                    <tbody id="carrito-body"></tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- ============ COLUMNA DERECHA: CLIENTE + PAGO ============ -->
    <div class="col-lg-7">

        <!-- Cliente -->
        <div class="card mb-3">
            <div class="card-header bg-white fw-semibold">
                <i class="bi bi-person-circle"></i> Cliente
            </div>
            <div class="card-body">
                <div class="row g-2">
                    <div class="col-md-6">
                        <label class="form-label small">Nombre *</label>
                        <input type="text" id="cliente-nombre" class="form-control" placeholder="Nombre del cliente">
                        <div id="cliente-info" class="small text-muted mt-1"></div>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small">Documento (opcional)</label>
                        <input type="text" id="cliente-documento" class="form-control">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small">Teléfono (opcional)</label>
                        <input type="text" id="cliente-telefono" class="form-control">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label small">Dirección (opcional)</label>
                        <input type="text" id="cliente-direccion" class="form-control">
                    </div>
                </div>
            </div>
        </div>

        <!-- Totales -->
        <div class="card mb-3">
            <div class="card-header bg-white fw-semibold">
                <i class="bi bi-cash-stack"></i> Totales
            </div>
            <div class="card-body">
                <div class="row g-2 align-items-center mb-2">
                    <div class="col-md-6">
                        <label class="form-label small mb-0">Subtotal</div>
                    </div>
                    <div class="col-md-6 text-end">
                        <span id="lbl-subtotal" class="fs-5">$0</span>
                    </div>
                </div>

                <div class="row g-2 align-items-center mb-2">
                    <div class="col-md-6">
                        <label class="form-label small mb-0">Método de pago</label>
                    </div>
                    <div class="col-md-6">
                        <select id="metodo-pago" class="form-select">
                            <option value="efectivo">Efectivo</option>
                            <option value="nequi">Nequi</option>
                            <option value="daviplata">Daviplata</option>
                            <option value="credito">Crédito</option>
                        </select>
                    </div>
                </div>

                <div class="row g-2 align-items-center mb-2">
                    <div class="col-md-6">
                        <label class="form-label small mb-0">Bolsas ($100 c/u)</label>
                    </div>
                    <div class="col-md-6">
                        <input type="number" id="bolsas" class="form-control" value="0" min="0" max="99">
                    </div>
                </div>

                <div id="fila-recargo" class="row g-2 align-items-center mb-2 d-none">
                    <div class="col-md-6">
                        <label class="form-label small mb-0">Recargo digital</label>
                    </div>
                    <div class="col-md-6 text-end">
                        <span id="lbl-recargo" class="text-muted">$0</span>
                    </div>
                </div>

                <hr>

                <div class="row g-2 align-items-center">
                    <div class="col-md-6">
                        <label class="form-label fw-bold mb-0 fs-5">TOTAL</label>
                    </div>
                    <div class="col-md-6 text-end">
                        <span id="lbl-total" class="fs-3 fw-bold text-success">$0</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Pago (solo si no es crédito) -->
        <div class="card mb-3" id="card-pago">
            <div class="card-body">
                <div class="row g-2 align-items-center">
                    <div class="col-md-6">
                        <label class="form-label mb-0 fw-semibold">Con cuánto paga</label>
                    </div>
                    <div class="col-md-6">
                        <div class="input-group input-group-lg">
                            <span class="input-group-text">$</span>
                            <input type="number" id="valor-pagado" class="form-control" value="0" min="0" step="50">
                        </div>
                    </div>
                </div>
                <div id="lbl-vueltas" class="text-end fs-5 mt-2"></div>
            </div>
        </div>

        <div class="alert alert-warning d-none" id="alerta-credito">
            <i class="bi bi-exclamation-triangle"></i>
            <strong>Venta a crédito:</strong> se sumará <span id="credito-monto">$0</span> al saldo del cliente.
        </div>

        <!-- Botones -->
        <div class="d-grid gap-2">
            <button type="button" id="btn-finalizar" class="btn btn-success btn-lg">
                <i class="bi bi-check-circle"></i> FINALIZAR VENTA
            </button>
            <button type="button" id="btn-limpiar" class="btn btn-outline-danger">
                <i class="bi bi-x-circle"></i> Limpiar todo
            </button>
        </div>
    </div>
</div>

<!-- Config para JS -->
<script>
    window.FACTURACION_CONFIG = {
        tiendaId: {{ tienda_id or 0 }},
        recargoPorcentaje: {{ recargo_porcentaje }},
        valorBolsa: {{ valor_bolsa }},
        urlBuscarProductos: "{{ url_for('facturacion.api_productos') }}",
        urlBuscarClientes: "{{ url_for('facturacion.api_clientes') }}",
        urlCrear: "{{ url_for('facturacion.crear') }}",
        urlTicket: "{{ url_for('facturacion.ticket', factura_id=0) }}".replace('/0/', '/'),
        csrfToken: "{{ csrf_token() }}",
    };
</script>
<script src="{{ url_for('static', filename='js/facturacion.js') }}"></script>
{% endblock %}
'''

ARCHIVOS['app/templates/facturacion/ticket.html'] = '''{% extends 'base.html' %}
{% block titulo %}Ticket {{ factura.numero_factura }}{% endblock %}

{% block contenido %}
<div class="row justify-content-center">
    <div class="col-md-8 col-lg-6">
        <div class="card shadow">
            <div class="card-body text-center">
                <div class="fs-1">🐱</div>
                <h4 class="fw-bold mb-0">EL MICHÍN DULCERÍA</h4>
                <p class="text-muted small mb-3">{{ factura.tienda.nombre }}</p>

                <div class="bg-light p-3 rounded mb-3">
                    <div class="text-success">
                        <i class="bi bi-check-circle fs-1"></i>
                    </div>
                    <h5 class="mt-2 mb-0">Venta registrada</h5>
                    <div class="text-muted small">Ticket {{ factura.numero_factura }}</div>
                </div>

                <table class="table table-sm text-start">
                    <tr><th>Cliente:</th><td>{{ cliente.nombre }}</td></tr>
                    {% if cliente.documento %}
                    <tr><th>Documento:</th><td>{{ cliente.documento }}</td></tr>
                    {% endif %}
                    <tr><th>Fecha:</th><td>{{ factura.fecha_hora.strftime('%d/%m/%Y %H:%M') }}</td></tr>
                    <tr><th>Método:</th><td>{{ factura.metodo_pago | upper }}</td></tr>
                </table>

                <table class="table table-sm">
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
                        <tr>
                            <th colspan="3" class="text-end">Subtotal</th>
                            <th class="text-end">${{ "{:,.0f}".format(factura.subtotal) }}</th>
                        </tr>
                        {% if factura.recargo_nequi > 0 %}
                        <tr>
                            <td colspan="3" class="text-end">Recargo digital</td>
                            <td class="text-end">${{ "{:,.0f}".format(factura.recargo_nequi) }}</td>
                        </tr>
                        {% endif %}
                        {% if factura.recargo_bolsa > 0 %}
                        <tr>
                            <td colspan="3" class="text-end">Bolsas</td>
                            <td class="text-end">${{ "{:,.0f}".format(factura.recargo_bolsa) }}</td>
                        </tr>
                        {% endif %}
                        <tr class="table-success">
                            <th colspan="3" class="text-end">TOTAL</th>
                            <th class="text-end">${{ "{:,.0f}".format(factura.total) }}</th>
                        </tr>
                        {% if factura.metodo_pago == 'credito' %}
                        <tr class="table-warning">
                            <th colspan="3" class="text-end">Saldo pendiente</th>
                            <th class="text-end">${{ "{:,.0f}".format(factura.saldo_pendiente) }}</th>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="3" class="text-end">Pagado</td>
                            <td class="text-end">${{ "{:,.0f}".format(factura.valor_pagado) }}</td>
                        </tr>
                        <tr>
                            <td colspan="3" class="text-end">Vueltas</td>
                            <td class="text-end">${{ "{:,.0f}".format(factura.vueltas) }}</td>
                        </tr>
                        {% endif %}
                    </tfoot>
                </table>

                <div class="d-grid gap-2 mt-4">
                    <a href="{{ url_for('facturacion.nueva') }}" class="btn btn-primary btn-lg">
                        <i class="bi bi-plus-circle"></i> Nueva venta
                    </a>
                    <button onclick="window.print()" class="btn btn-outline-secondary">
                        <i class="bi bi-printer"></i> Imprimir
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''

# ==================== JAVASCRIPT ====================
ARCHIVOS['app/static/js/facturacion.js'] = '''// app/static/js/facturacion.js
(function() {
    'use strict';

    const CFG = window.FACTURACION_CONFIG || {};
    const carrito = [];

    // ==================== HELPERS ====================
    function fmt(n) {
        return '$' + Math.round(n || 0).toLocaleString('es-CO');
    }

    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }

    // ==================== CALCULO DE PRECIO ====================
    function calcularPrecioProducto(prod, cantidad) {
        // Aplicar condiciones por cantidad
        const cant = parseInt(cantidad);
        const c3 = prod.condicion3 ? parseInt(prod.condicion3) : null;
        const c2 = prod.condicion2 ? parseInt(prod.condicion2) : null;
        const c1 = prod.condicion1 ? parseInt(prod.condicion1) : null;

        if (c3 && cant >= c3 && prod.precio3 > 0) return prod.precio3;
        if (c2 && cant >= c2 && prod.precio2 > 0) return prod.precio2;
        if (c1 && cant >= c1 && prod.precio1 > 0) return prod.precio1;
        return prod.precio || 0;
    }

    // ==================== BUSQUEDA DE PRODUCTOS ====================
    const inputBuscar = $('#input-buscar');
    const resultados = $('#resultados');
    let timeoutBuscar = null;

    inputBuscar.addEventListener('input', function() {
        clearTimeout(timeoutBuscar);
        const q = this.value.trim();
        if (q.length < 2) {
            resultados.innerHTML = '';
            return;
        }
        timeoutBuscar = setTimeout(() => buscarProductos(q), 250);
    });

    inputBuscar.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            // Si hay un solo resultado, agregarlo
            const items = resultados.querySelectorAll('.list-group-item');
            if (items.length === 1) {
                items[0].click();
            } else if (items.length > 0) {
                items[0].click();
            }
        }
    });

    async function buscarProductos(q) {
        try {
            const r = await fetch(CFG.urlBuscarProductos + '?q=' + encodeURIComponent(q));
            const data = await r.json();
            pintarResultados(data);
        } catch (e) {
            console.error('Error buscando productos:', e);
        }
    }

    function pintarResultados(data) {
        resultados.innerHTML = '';
        if (!data.length) {
            resultados.innerHTML = '<div class="list-group-item text-muted">Sin resultados</div>';
            return;
        }
        data.forEach(p => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';

            const stockClass = p.stock === 0 ? 'text-danger' : (p.stock <= 5 ? 'text-warning' : 'text-success');
            const stockIcon = p.stock === 0 ? '🔴' : (p.stock <= 5 ? '🟡' : '🟢');

            item.innerHTML = `
                <div class="text-start">
                    <div class="fw-semibold">${p.nombre}</div>
                    <small class="text-muted">${p.codigo || ''}</small>
                </div>
                <div class="text-end">
                    <div class="fw-bold">${fmt(p.precio)}</div>
                    <small class="${stockClass}">${stockIcon} ${p.stock}</small>
                </div>
            `;
            item.addEventListener('click', () => agregarAlCarrito(p));
            resultados.appendChild(item);
        });
    }

    // ==================== CARRITO ====================
    function agregarAlCarrito(prod) {
        if (prod.stock <= 0) {
            alert('Producto sin stock');
            return;
        }

        // Pedir cantidad
        const cantStr = prompt(`¿Cuántas unidades de "${prod.nombre}"?\\n(Máximo disponible: ${prod.stock})`, '1');
        if (cantStr === null) return;

        const cantidad = parseInt(cantStr);
        if (isNaN(cantidad) || cantidad <= 0) {
            alert('Cantidad invalida');
            return;
        }
        if (cantidad > prod.stock) {
            alert(`Solo hay ${prod.stock} unidades disponibles`);
            return;
        }

        // Verificar si ya existe
        const existente = carrito.find(it => it.producto_id === prod.id);
        if (existente) {
            const nuevaCant = existente.cantidad + cantidad;
            if (nuevaCant > prod.stock) {
                alert(`Solo hay ${prod.stock} unidades en total`);
                return;
            }
            existente.cantidad = nuevaCant;
            existente.precio_unitario = calcularPrecioProducto(prod, nuevaCant);
            existente.subtotal = existente.precio_unitario * nuevaCant;
        } else {
            carrito.push({
                producto_id: prod.id,
                nombre: prod.nombre,
                cantidad: cantidad,
                precio_unitario: calcularPrecioProducto(prod, cantidad),
                subtotal: calcularPrecioProducto(prod, cantidad) * cantidad,
                stock_max: prod.stock,
                prod_data: prod,
            });
        }

        // Limpiar busqueda
        inputBuscar.value = '';
        resultados.innerHTML = '';
        inputBuscar.focus();

        renderCarrito();
    }

    function renderCarrito() {
        const body = $('#carrito-body');
        const tabla = $('#carrito-tabla');
        const vacio = $('#carrito-vacio');
        const count = $('#carrito-count');

        body.innerHTML = '';
        count.textContent = carrito.length;

        if (carrito.length === 0) {
            tabla.classList.add('d-none');
            vacio.classList.remove('d-none');
        } else {
            tabla.classList.remove('d-none');
            vacio.classList.add('d-none');
            carrito.forEach((item, idx) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>
                        <div class="fw-semibold small">${item.nombre}</div>
                    </td>
                    <td class="text-center">
                        <input type="number" class="form-control form-control-sm text-center" 
                               value="${item.cantidad}" min="1" max="${item.stock_max}"
                               data-idx="${idx}" data-accion="cantidad" style="width: 65px;">
                    </td>
                    <td class="text-end small">${fmt(item.precio_unitario)}</td>
                    <td class="text-end small fw-semibold">${fmt(item.subtotal)}</td>
                    <td>
                        <button type="button" class="btn btn-sm btn-outline-danger" data-idx="${idx}" data-accion="eliminar">
                            <i class="bi bi-x"></i>
                        </button>
                    </td>
                `;
                body.appendChild(tr);
            });

            // Listeners
            body.querySelectorAll('input[data-accion="cantidad"]').forEach(inp => {
                inp.addEventListener('change', function() {
                    const idx = parseInt(this.dataset.idx);
                    let cant = parseInt(this.value);
                    const item = carrito[idx];
                    if (isNaN(cant) || cant < 1) cant = 1;
                    if (cant > item.stock_max) {
                        cant = item.stock_max;
                        alert(`Máximo ${item.stock_max} unidades`);
                    }
                    item.cantidad = cant;
                    item.precio_unitario = calcularPrecioProducto(item.prod_data, cant);
                    item.subtotal = item.precio_unitario * cant;
                    renderCarrito();
                });
            });

            body.querySelectorAll('button[data-accion="eliminar"]').forEach(btn => {
                btn.addEventListener('click', function() {
                    const idx = parseInt(this.dataset.idx);
                    carrito.splice(idx, 1);
                    renderCarrito();
                });
            });
        }

        renderTotales();
    }

    // ==================== TOTALES ====================
    function renderTotales() {
        const subtotal = carrito.reduce((s, it) => s + it.subtotal, 0);
        const metodo = $('#metodo-pago').value;
        const bolsas = parseInt($('#bolsas').value) || 0;
        const totalBolsas = bolsas * CFG.valorBolsa;

        let recargo = 0;
        if (metodo === 'nequi' || metodo === 'daviplata') {
            recargo = subtotal * (CFG.recargoPorcentaje / 100);
        }

        const total = subtotal + recargo + totalBolsas;

        $('#lbl-subtotal').textContent = fmt(subtotal);
        $('#lbl-total').textContent = fmt(total);

        // Recargo
        if (recargo > 0) {
            $('#fila-recargo').classList.remove('d-none');
            $('#lbl-recargo').textContent = fmt(recargo) + ` (${CFG.recargoPorcentaje}%)`;
        } else {
            $('#fila-recargo').classList.add('d-none');
        }

        // Credito
        if (metodo === 'credito') {
            $('#card-pago').classList.add('d-none');
            $('#alerta-credito').classList.remove('d-none');
            $('#credito-monto').textContent = fmt(total);
        } else {
            $('#card-pago').classList.remove('d-none');
            $('#alerta-credito').classList.add('d-none');

            const pagado = parseFloat($('#valor-pagado').value) || 0;
            const vueltas = pagado - total;
            if (pagado > 0) {
                if (vueltas >= 0) {
                    $('#lbl-vueltas').innerHTML = `<span class="text-success">Vueltas: ${fmt(vueltas)}</span>`;
                } else {
                    $('#lbl-vueltas').innerHTML = `<span class="text-danger">Faltan: ${fmt(-vueltas)}</span>`;
                }
            } else {
                $('#lbl-vueltas').innerHTML = '';
            }
        }
    }

    // ==================== EVENTOS TOTALLES ====================
    $('#metodo-pago').addEventListener('change', renderTotales);
    $('#bolsas').addEventListener('input', renderTotales);
    $('#valor-pagado').addEventListener('input', renderTotales);

    // ==================== FINALIZAR ====================
    $('#btn-finalizar').addEventListener('click', async function() {
        if (carrito.length === 0) {
            alert('El carrito está vacío');
            return;
        }

        const nombre = $('#cliente-nombre').value.trim();
        if (!nombre) {
            alert('Ingresa el nombre del cliente');
            $('#cliente-nombre').focus();
            return;
        }

        const metodo = $('#metodo-pago').value;
        const bolsas = parseInt($('#bolsas').value) || 0;
        const valorPagado = parseFloat($('#valor-pagado').value) || 0;

        const subtotal = carrito.reduce((s, it) => s + it.subtotal, 0);
        let recargo = 0;
        if (metodo === 'nequi' || metodo === 'daviplata') {
            recargo = subtotal * (CFG.recargoPorcentaje / 100);
        }
        const totalBolsas = bolsas * CFG.valorBolsa;
        const total = subtotal + recargo + totalBolsas;

        if (metodo !== 'credito') {
            if (valorPagado < total - 0.01) {
                alert(`Faltan ${fmt(total - valorPagado)} para completar el pago`);
                return;
            }
        }

        const payload = {
            cliente: {
                nombre: nombre,
                documento: $('#cliente-documento').value.trim(),
                telefono: $('#cliente-telefono').value.trim(),
                direccion: $('#cliente-direccion').value.trim(),
            },
            carrito: carrito.map(it => ({
                producto_id: it.producto_id,
                cantidad: it.cantidad,
                precio_unitario: it.precio_unitario,
            })),
            metodo_pago: metodo,
            recargo_porcentaje: CFG.recargoPorcentaje,
            bolsas: bolsas,
            valor_pagado: valorPagado,
        };

        const btn = this;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

        try {
            const r = await fetch(CFG.urlCrear, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CFG.csrfToken,
                },
                body: JSON.stringify(payload),
            });
            const data = await r.json();

            if (data.ok) {
                window.location.href = data.redirect;
            } else {
                alert('Error: ' + (data.error || 'Desconocido'));
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-check-circle"></i> FINALIZAR VENTA';
            }
        } catch (e) {
            alert('Error de conexión: ' + e.message);
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle"></i> FINALIZAR VENTA';
        }
    });

    // ==================== LIMPIAR ====================
    $('#btn-limpiar').addEventListener('click', function() {
        if (!confirm('¿Limpiar toda la venta?')) return;
        carrito.length = 0;
        renderCarrito();
        $('#cliente-nombre').value = '';
        $('#cliente-documento').value = '';
        $('#cliente-telefono').value = '';
        $('#cliente-direccion').value = '';
        $('#valor-pagado').value = '0';
        $('#bolsas').value = '0';
        $('#cliente-info').textContent = '';
        inputBuscar.focus();
    });

    // ==================== AUTOCOMPLETE CLIENTE ====================
    let timeoutCliente = null;
    $('#cliente-nombre').addEventListener('input', function() {
        clearTimeout(timeoutCliente);
        const q = this.value.trim();
        if (q.length < 3) {
            $('#cliente-info').textContent = '';
            return;
        }
        timeoutCliente = setTimeout(async () => {
            try {
                const r = await fetch(CFG.urlBuscarClientes + '?q=' + encodeURIComponent(q));
                const data = await r.json();
                if (data.length > 0) {
                    const c = data[0];
                    $('#cliente-info').innerHTML = `<i class="bi bi-info-circle"></i> Cliente existente - Saldo: ${fmt(c.saldo)}`;
                } else {
                    $('#cliente-info').innerHTML = '<i class="bi bi-plus-circle text-success"></i> Se creará un cliente nuevo';
                }
            } catch (e) {
                console.error(e);
            }
        }, 400);
    });

    // ==================== SELECTOR DE TIENDA ====================
    const selectorTienda = $('#selector-tienda');
    if (selectorTienda) {
        selectorTienda.addEventListener('change', function() {
            const url = new URL(window.location.href);
            url.searchParams.set('tienda', this.value);
            window.location.href = url.toString();
        });
    }

    // ==================== INIT ====================
    inputBuscar.focus();
    renderCarrito();

})();
'''


def main():
    print(f'Creando modulo de facturacion en: {RAIZ}')
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