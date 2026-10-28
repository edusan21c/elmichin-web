# scripts/crear_venta_rapida.py
# Modulo de Venta Rapida (escaneo + facturacion en 3 clicks).
# Ejecutar UNA VEZ: python scripts\crear_venta_rapida.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== BLUEPRINT ====================
ARCHIVOS['app/blueprints/venta_rapida/__init__.py'] = '''# app/blueprints/venta_rapida/__init__.py
from flask import Blueprint

bp = Blueprint('venta_rapida', __name__, url_prefix='/venta-rapida')

from . import routes  # noqa: E402, F401
'''

ARCHIVOS['app/blueprints/venta_rapida/routes.py'] = '''# app/blueprints/venta_rapida/routes.py
from decimal import Decimal
from flask import render_template, request, jsonify, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_
from . import bp
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.tienda import Tienda
from app.services.facturacion_service import crear_factura_completa


def tienda_actual():
    if current_user.es_programador():
        tid = request.args.get('tienda', type=int)
        if tid:
            return tid
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None
    return current_user.tienda_id


@bp.route('/')
@login_required
def nueva():
    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()
    return render_template(
        'venta_rapida/nueva.html',
        tienda_id=tienda_id,
        tiendas=tiendas,
    )


@bp.route('/api/productos')
@login_required
def api_productos():
    """Busqueda rapida de productos (por nombre o codigo)."""
    q = request.args.get('q', '', type=str).strip()
    if not q:
        return jsonify([])

    tienda_id = tienda_actual()
    if not tienda_id:
        return jsonify([])

    # Buscar por codigo exacto primero, luego por nombre
    producto = Producto.query.filter_by(codigo_barras=q).first()
    productos = [producto] if producto else []

    if not productos:
        productos = (Producto.query
                     .filter(Producto.nombre.ilike(f'%{q}%'))
                     .order_by(Producto.nombre)
                     .limit(5)
                     .all())

    resultados = []
    for p in productos:
        pres = ProductoTienda.query.filter_by(
            producto_id=p.id, tienda_id=tienda_id
        ).first()
        if not pres or pres.cantidad <= 0:
            continue
        resultados.append({
            'id': p.id,
            'nombre': p.nombre,
            'codigo': p.codigo_barras or '',
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


@bp.route('/crear', methods=['POST'])
@login_required
def crear():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'error': 'Datos invalidos'}), 400

    tienda_id = tienda_actual()
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'No hay tienda activa'}), 400

    carrito = data.get('carrito', [])
    if not carrito:
        return jsonify({'ok': False, 'error': 'El carrito esta vacio'}), 400

    # Calcular total exacto
    try:
        total = sum(
            Decimal(str(it['precio_unitario'])) * int(it['cantidad'])
            for it in carrito
        )
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Error calculando total: {e}'}), 400

    try:
        factura_id, error = crear_factura_completa(
            tienda_id=tienda_id,
            usuario_id=current_user.id,
            cliente_data={'nombre': 'Venta Rápida'},
            carrito=carrito,
            metodo_pago='efectivo',
            recargo_porcentaje=Decimal('0'),
            bolsas_cantidad=0,
            valor_bolsa=Decimal('0'),
            valor_pagado=total,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': f'Error del servidor: {e}'}), 500

    if error:
        return jsonify({'ok': False, 'error': error}), 400

    return jsonify({
        'ok': True,
        'factura_id': factura_id,
        'redirect': url_for('facturacion.ticket', factura_id=factura_id),
    })
'''

# ==================== TEMPLATE ====================
ARCHIVOS['app/templates/venta_rapida/nueva.html'] = '''{% extends 'base.html' %}
{% block titulo %}Venta Rápida{% endblock %}

{% block contenido %}
<div class="row g-3">
    <!-- ==================== COLUMNA IZQUIERDA: BUSQUEDA ==================== -->
    <div class="col-lg-7">
        <div class="card border-success">
            <div class="card-header bg-success text-white">
                <div class="d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">
                        <i class="bi bi-lightning-charge"></i> Venta Rápida
                    </h5>
                    {% if current_user.es_programador() and tiendas|length > 1 %}
                    <select id="selector-tienda" class="form-select form-select-sm" style="width:auto;">
                        {% for t in tiendas %}
                        <option value="{{ t.id }}" {% if t.id == tienda_id %}selected{% endif %}>{{ t.nombre }}</option>
                        {% endfor %}
                    </select>
                    {% endif %}
                </div>
            </div>
            <div class="card-body">
                <label class="form-label fw-semibold">
                    <i class="bi bi-upc-scan"></i> Escanea o escribe el código
                </label>
                <div class="input-group input-group-lg mb-2">
                    <span class="input-group-text"><i class="bi bi-search"></i></span>
                    <input type="text" id="input-buscar" class="form-control"
                           placeholder="Escanea o escribe..." autocomplete="off" autofocus>
                </div>
                <div id="resultados" class="list-group" style="max-height: 300px; overflow-y: auto;"></div>
            </div>
        </div>

        <!-- Carrito -->
        <div class="card mt-3">
            <div class="card-header bg-dark text-white d-flex justify-content-between">
                <span><i class="bi bi-cart3"></i> Carrito</span>
                <span id="carrito-count" class="badge bg-light text-dark">0</span>
            </div>
            <div class="card-body p-0">
                <div id="carrito-vacio" class="text-center text-muted py-4">
                    <i class="bi bi-cart-x fs-1 d-block mb-2"></i>
                    Escanea el primer producto
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

    <!-- ==================== COLUMNA DERECHA: TOTAL + COBRO ==================== -->
    <div class="col-lg-5">
        <div class="card border-success sticky-top" style="top: 80px;">
            <div class="card-body text-center">
                <div class="text-muted small">TOTAL A COBRAR</div>
                <div id="lbl-total" class="display-3 fw-bold text-success mb-3">$0</div>

                <div class="mb-3">
                    <label class="form-label">Con cuánto paga</label>
                    <div class="input-group input-group-lg">
                        <span class="input-group-text">$</span>
                        <input type="number" id="input-pagado" class="form-control text-end"
                               placeholder="0" min="0" step="100">
                    </div>
                    <div id="lbl-vueltas" class="fs-4 mt-2"></div>
                </div>

                <button type="button" id="btn-finalizar" class="btn btn-success btn-lg w-100 mb-2">
                    <i class="bi bi-check-circle"></i> COBRAR
                </button>
                <button type="button" id="btn-limpiar" class="btn btn-outline-danger w-100 btn-sm">
                    Limpiar
                </button>
            </div>
        </div>

        <!-- Últimas ventas (mini historial) -->
        <div class="card mt-3">
            <div class="card-header bg-white small fw-semibold">
                <i class="bi bi-clock-history"></i> Últimas ventas de hoy
            </div>
            <div class="card-body p-0">
                <div id="historial" class="list-group list-group-flush" style="max-height: 200px; overflow-y: auto;">
                    <div class="text-center text-muted py-3 small">Sin ventas todavía</div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Config para JS -->
<script>
    window.VR_CONFIG = {
        tiendaId: {{ tienda_id or 0 }},
        urlBuscarProductos: "{{ url_for('venta_rapida.api_productos') }}",
        urlCrear: "{{ url_for('venta_rapida.crear') }}",
        csrfToken: "{{ csrf_token() }}",
    };
</script>
<script src="{{ url_for('static', filename='js/venta_rapida.js') }}"></script>
{% endblock %}
'''

# ==================== JAVASCRIPT ====================
ARCHIVOS['app/static/js/venta_rapida.js'] = '''// app/static/js/venta_rapida.js
(function() {
    'use strict';

    const CFG = window.VR_CONFIG || {};
    const carrito = [];
    const historial = [];

    function fmt(n) {
        return '$' + Math.round(n || 0).toLocaleString('es-CO');
    }

    function $(sel) { return document.querySelector(sel); }

    // ==================== CALCULO DE PRECIO ====================
    function calcularPrecio(prod, cantidad) {
        const cant = parseInt(cantidad);
        const c3 = prod.condicion3 ? parseInt(prod.condicion3) : null;
        const c2 = prod.condicion2 ? parseInt(prod.condicion2) : null;
        const c1 = prod.condicion1 ? parseInt(prod.condicion1) : null;

        if (c3 && cant >= c3 && prod.precio3 > 0) return prod.precio3;
        if (c2 && cant >= c2 && prod.precio2 > 0) return prod.precio2;
        if (c1 && cant >= c1 && prod.precio1 > 0) return prod.precio1;
        return prod.precio || 0;
    }

    // ==================== BUSQUEDA ====================
    const inputBuscar = $('#input-buscar');
    const resultados = $('#resultados');
    let timeout = null;

    inputBuscar.addEventListener('input', function() {
        clearTimeout(timeout);
        const q = this.value.trim();
        if (!q) {
            resultados.innerHTML = '';
            return;
        }
        timeout = setTimeout(() => buscar(q), 150);
    });

    inputBuscar.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            // Si hay resultado único, agregarlo
            const items = resultados.querySelectorAll('.list-group-item');
            if (items.length >= 1) {
                items[0].click();
            }
        }
    });

    async function buscar(q) {
        try {
            const r = await fetch(CFG.urlBuscarProductos + '?q=' + encodeURIComponent(q));
            const data = await r.json();
            pintarResultados(data);
        } catch (e) {
            console.error(e);
        }
    }

    function pintarResultados(data) {
        resultados.innerHTML = '';
        if (!data.length) {
            resultados.innerHTML = '<div class="list-group-item text-muted text-center py-3">Sin resultados o sin stock</div>';
            return;
        }
        data.forEach(p => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center py-2';
            item.innerHTML = `
                <div class="text-start">
                    <div class="fw-semibold">${p.nombre}</div>
                    <small class="text-muted">${p.codigo || ''}</small>
                </div>
                <div class="text-end">
                    <div class="fw-bold text-success">${fmt(p.precio)}</div>
                    <small class="text-muted">Stock: ${p.stock}</small>
                </div>
            `;
            item.addEventListener('click', () => agregarAlCarrito(p));
            resultados.appendChild(item);
        });
    }

    // ==================== AGREGAR AL CARRITO ====================
    function agregarAlCarrito(prod) {
        // Verificar si ya existe
        const existente = carrito.find(it => it.producto_id === prod.id);

        if (existente) {
            const nuevaCant = existente.cantidad + 1;
            if (nuevaCant > prod.stock) {
                alert(`Solo hay ${prod.stock} unidades disponibles`);
                return;
            }
            existente.cantidad = nuevaCant;
            existente.precio_unitario = calcularPrecio(prod, nuevaCant);
            existente.subtotal = existente.precio_unitario * nuevaCant;
        } else {
            // Preguntar cantidad (default 1 si es por codigo de barras)
            let cantidad = 1;
            // Si no es codigo exacto (múltiples resultados), pedir cantidad
            const input = inputBuscar.value.trim();
            if (input !== prod.codigo) {
                const resp = prompt(`¿Cuántas unidades de "${prod.nombre}"?`, '1');
                if (resp === null) return;
                cantidad = parseInt(resp);
                if (isNaN(cantidad) || cantidad <= 0) return;
                if (cantidad > prod.stock) {
                    alert(`Solo hay ${prod.stock} unidades`);
                    return;
                }
            }

            carrito.push({
                producto_id: prod.id,
                nombre: prod.nombre,
                cantidad: cantidad,
                precio_unitario: calcularPrecio(prod, cantidad),
                subtotal: calcularPrecio(prod, cantidad) * cantidad,
                stock_max: prod.stock,
                prod_data: prod,
            });
        }

        // Limpiar búsqueda y volver a enfocar
        inputBuscar.value = '';
        resultados.innerHTML = '';
        inputBuscar.focus();

        renderCarrito();
    }

    // ==================== RENDER CARRITO ====================
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
                    <td><div class="fw-semibold small">${item.nombre}</div></td>
                    <td class="text-center">
                        <input type="number" class="form-control form-control-sm text-center"
                               value="${item.cantidad}" min="1" max="${item.stock_max}"
                               data-idx="${idx}" data-accion="cantidad" style="width: 65px;">
                    </td>
                    <td class="text-end small">${fmt(item.precio_unitario)}</td>
                    <td class="text-end small fw-semibold">${fmt(item.subtotal)}</td>
                    <td>
                        <button type="button" class="btn btn-sm btn-outline-danger"
                                data-idx="${idx}" data-accion="eliminar">
                            <i class="bi bi-x"></i>
                        </button>
                    </td>
                `;
                body.appendChild(tr);
            });

            body.querySelectorAll('input[data-accion="cantidad"]').forEach(inp => {
                inp.addEventListener('change', function() {
                    const idx = parseInt(this.dataset.idx);
                    let cant = parseInt(this.value);
                    const item = carrito[idx];
                    if (isNaN(cant) || cant < 1) cant = 1;
                    if (cant > item.stock_max) {
                        cant = item.stock_max;
                        alert(`Máximo ${item.stock_max}`);
                    }
                    item.cantidad = cant;
                    item.precio_unitario = calcularPrecio(item.prod_data, cant);
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

        renderTotal();
    }

    // ==================== TOTAL + VUELTAS ====================
    function renderTotal() {
        const total = carrito.reduce((s, it) => s + it.subtotal, 0);
        $('#lbl-total').textContent = fmt(total);

        const pagado = parseFloat($('#input-pagado').value) || 0;
        if (pagado > 0) {
            const vueltas = pagado - total;
            if (vueltas >= 0) {
                $('#lbl-vueltas').innerHTML = `<span class="text-success">Vueltas: ${fmt(vueltas)}</span>`;
            } else {
                $('#lbl-vueltas').innerHTML = `<span class="text-danger">Faltan: ${fmt(-vueltas)}</span>`;
            }
        } else {
            $('#lbl-vueltas').innerHTML = '';
        }
    }

    $('#input-pagado').addEventListener('input', renderTotal);

    // ==================== COBRAR ====================
    $('#btn-finalizar').addEventListener('click', async function() {
        if (carrito.length === 0) {
            alert('El carrito está vacío');
            return;
        }

        const total = carrito.reduce((s, it) => s + it.subtotal, 0);
        const pagado = parseFloat($('#input-pagado').value) || 0;

        if (pagado < total - 0.01) {
            alert(`Faltan ${fmt(total - pagado)} para completar el pago`);
            return;
        }

        const payload = {
            carrito: carrito.map(it => ({
                producto_id: it.producto_id,
                cantidad: it.cantidad,
                precio_unitario: it.precio_unitario,
            })),
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
                // Guardar en historial
                historial.unshift({
                    factura: data.factura_id,
                    total: total,
                    hora: new Date().toLocaleTimeString('es-CO', {hour: '2-digit', minute: '2-digit'}),
                    items: carrito.length,
                });
                renderHistorial();

                // Limpiar carrito
                carrito.length = 0;
                renderCarrito();
                $('#input-pagado').value = '';
                $('#lbl-vueltas').innerHTML = '';
                inputBuscar.focus();

                // Feedback visual
                mostrarAlerta('✅ Venta registrada', 'success');
            } else {
                alert('Error: ' + (data.error || 'Desconocido'));
            }
        } catch (e) {
            alert('Error de conexión: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle"></i> COBRAR';
        }
    });

    // ==================== LIMPIAR ====================
    $('#btn-limpiar').addEventListener('click', function() {
        if (carrito.length > 0 && !confirm('¿Limpiar toda la venta?')) return;
        carrito.length = 0;
        renderCarrito();
        $('#input-pagado').value = '';
        $('#lbl-vueltas').innerHTML = '';
        inputBuscar.focus();
    });

    // ==================== HISTORIAL ====================
    function renderHistorial() {
        const h = $('#historial');
        if (historial.length === 0) {
            h.innerHTML = '<div class="text-center text-muted py-3 small">Sin ventas todavía</div>';
            return;
        }
        h.innerHTML = historial.slice(0, 10).map(v => `
            <div class="list-group-item d-flex justify-content-between py-2 small">
                <div>
                    <strong>${v.items}</strong> producto${v.items !== 1 ? 's' : ''}
                    <span class="text-muted">· ${v.hora}</span>
                </div>
                <div class="text-success fw-bold">${fmt(v.total)}</div>
            </div>
        `).join('');
    }

    // ==================== ALERTA FLOTANTE ====================
    function mostrarAlerta(msg, tipo) {
        const div = document.createElement('div');
        div.className = `alert alert-${tipo} position-fixed top-0 start-50 translate-middle-x mt-3 shadow`;
        div.style.zIndex = '9999';
        div.innerHTML = msg;
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 2000);
    }

    // ==================== SELECTOR DE TIENDA ====================
    const st = $('#selector-tienda');
    if (st) {
        st.addEventListener('change', function() {
            const url = new URL(window.location.href);
            url.searchParams.set('tienda', this.value);
            window.location.href = url.toString();
        });
    }

    // ==================== INICIALIZACION ====================
    inputBuscar.focus();
    renderCarrito();
    renderHistorial();

})();
'''

# ==================== UPDATE SIDEBAR ====================
ARCHIVOS['app/templates/layout/sidebar.html'] = '''<nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar border-end" style="min-height: calc(100vh - 56px);">
    <div class="position-sticky pt-3">
        <ul class="nav flex-column">
            <li class="nav-item">
                <a class="nav-link {% if request.endpoint == 'dashboard.index' %}active{% endif %}"
                   href="{{ url_for('dashboard.index') }}">
                    <i class="bi bi-house-door"></i> Inicio
                </a>
            </li>

            {% if current_user.rol in ('admin', 'programador') %}
            <li class="nav-item">
                <a class="nav-link {% if request.blueprint == 'inventario' %}active{% endif %}"
                   href="{{ url_for('inventario.lista') }}">
                    <i class="bi bi-box-seam"></i> Inventario
                </a>
            </li>
            {% endif %}

            {% if current_user.rol in ('admin', 'programador', 'operario') %}
            <li class="nav-item">
                <a class="nav-link {% if request.blueprint == 'facturacion' %}active{% endif %}"
                   href="{{ url_for('facturacion.nueva') }}">
                    <i class="bi bi-receipt"></i> Facturación
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link {% if request.blueprint == 'venta_rapida' %}active{% endif %}"
                   href="{{ url_for('venta_rapida.nueva') }}">
                    <i class="bi bi-lightning-charge"></i> Venta Rápida
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link {% if request.blueprint == 'reportes' and request.endpoint != 'reportes.cuentas_por_cobrar' %}active{% endif %}"
                   href="{{ url_for('reportes.ventas') }}">
                    <i class="bi bi-graph-up"></i> Reportes
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link {% if request.endpoint == 'reportes.cuentas_por_cobrar' %}active{% endif %}"
                   href="{{ url_for('reportes.cuentas_por_cobrar') }}">
                    <i class="bi bi-cash-coin"></i> CxC
                </a>
            </li>
            {% endif %}

            {% if current_user.rol in ('admin', 'programador') %}
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-bar-chart"></i> Estadísticas
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            {% endif %}

            {% if current_user.rol == 'programador' %}
            <li class="nav-item mt-3">
                <small class="text-muted ps-3">ADMINISTRACIÓN</small>
            </li>
            <li class="nav-item">
                <a class="nav-link {% if request.blueprint == 'admin' %}active{% endif %}"
                   href="{{ url_for('admin.lista_usuarios') }}">
                    <i class="bi bi-people"></i> Usuarios
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-gear"></i> Configuración
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            {% endif %}
        </ul>
    </div>
</nav>
'''


def main():
    print(f'Creando modulo de Venta Rapida en: {RAIZ}')
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