# scripts/crear_stock_masivo.py
# 1) Arregla el import de Cliente en facturacion.
# 2) Crea el modulo de stock masivo en inventario.
# Ejecutar: python scripts\crear_stock_masivo.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== FIX: routes.py de facturacion ====================
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
from app.models.cliente import Cliente
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

# ==================== ROUTES DE INVENTARIO CON STOCK MASIVO ====================
ARCHIVOS['app/blueprints/inventario/routes.py'] = '''# app/blueprints/inventario/routes.py
from flask import render_template, redirect, url_for, flash, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from . import bp
from .forms import ProductoForm, StockForm
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.tienda import Tienda
from app.utils.decorators import admin_requerido, programador_requerido


def tienda_actual():
    if current_user.es_programador():
        tid = request.args.get('tienda', type=int)
        if tid:
            return tid
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None
    return current_user.tienda_id


def puede_editar():
    return current_user.es_admin()


# ==================== LISTA ====================
@bp.route('/')
@login_required
def lista():
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '', type=str).strip()
    filtro_stock = request.args.get('filtro', '', type=str).strip()  # '', 'sin_stock', 'bajo'
    tienda_id = tienda_actual()
    per_page = 20

    query = Producto.query

    if busqueda:
        query = query.filter(
            or_(
                Producto.nombre.ilike(f'%{busqueda}%'),
                Producto.codigo_barras.ilike(f'%{busqueda}%')
            )
        )

    query = query.order_by(Producto.nombre)

    # Si hay filtro de stock, no paginamos del lado del servidor (limitamos)
    if filtro_stock and tienda_id:
        # Necesitamos filtrar por stock, hacer JOIN
        sub = db.session.query(ProductoTienda.producto_id).filter(
            ProductoTienda.tienda_id == tienda_id
        )
        if filtro_stock == 'sin_stock':
            sub = sub.filter(ProductoTienda.cantidad <= 0)
        elif filtro_stock == 'bajo':
            sub = sub.filter(ProductoTienda.cantidad.between(1, 5))
        query = query.filter(Producto.id.in_(sub))

    paginacion = query.paginate(page=page, per_page=per_page, error_out=False)

    productos_con_info = []
    for prod in paginacion.items:
        pres = None
        if tienda_id:
            pres = ProductoTienda.query.filter_by(
                producto_id=prod.id, tienda_id=tienda_id
            ).first()
        productos_con_info.append({
            'producto': prod,
            'presentacion': pres,
            'stock': pres.cantidad if pres else 0,
            'precio_venta': float(pres.precio_venta) if pres and pres.precio_venta else 0,
        })

    tiendas = Tienda.query.filter_by(activa=True).all()

    # Contadores para los filtros
    contadores = {'total': 0, 'sin_stock': 0, 'bajo': 0}
    if tienda_id:
        contadores['total'] = ProductoTienda.query.filter_by(tienda_id=tienda_id).count()
        contadores['sin_stock'] = ProductoTienda.query.filter_by(
            tienda_id=tienda_id).filter(ProductoTienda.cantidad <= 0).count()
        contadores['bajo'] = ProductoTienda.query.filter_by(
            tienda_id=tienda_id).filter(
            ProductoTienda.cantidad.between(1, 5)).count()

    return render_template(
        'inventario/lista.html',
        productos=productos_con_info,
        paginacion=paginacion,
        busqueda=busqueda,
        filtro_stock=filtro_stock,
        tienda_id=tienda_id,
        tiendas=tiendas,
        puede_editar=puede_editar(),
        contadores=contadores,
    )


# ==================== CREAR ====================
@bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_requerido
def nuevo():
    form = ProductoForm()
    if form.validate_on_submit():
        existente = Producto.query.filter_by(nombre=form.nombre.data.strip()).first()
        if existente:
            flash('Ya existe un producto con ese nombre.', 'danger')
            return render_template('inventario/form.html', form=form, producto=None)

        producto = Producto(
            nombre=form.nombre.data.strip(),
            codigo_barras=form.codigo_barras.data.strip() if form.codigo_barras.data else None,
            categoria=form.categoria.data or None,
        )
        db.session.add(producto)
        db.session.flush()

        for tienda in Tienda.query.filter_by(activa=True).all():
            pres = ProductoTienda(
                producto_id=producto.id,
                tienda_id=tienda.id,
                cantidad=0,
                precio_proveedor=form.precio_proveedor.data or 0,
                precio_proveedor2=form.precio_proveedor2.data or 0,
                precio_proveedor3=form.precio_proveedor3.data or 0,
                porcentaje=form.porcentaje.data or 0,
                precio_venta=form.precio_venta.data or 0,
                condicion1=form.condicion1.data or '',
                precio_venta1=form.precio_venta1.data or 0,
                condicion2=form.condicion2.data or '',
                precio_venta2=form.precio_venta2.data or 0,
                condicion3=form.condicion3.data or '',
                precio_venta3=form.precio_venta3.data or 0,
            )
            db.session.add(pres)

        db.session.commit()
        flash(f'Producto "{producto.nombre}" creado correctamente.', 'success')
        return redirect(url_for('inventario.lista'))

    return render_template('inventario/form.html', form=form, producto=None)


# ==================== EDITAR ====================
@bp.route('/<int:producto_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_requerido
def editar(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    tienda_id = tienda_actual() or 1
    pres = ProductoTienda.query.filter_by(
        producto_id=producto.id, tienda_id=tienda_id
    ).first()

    if pres is None:
        pres = ProductoTienda(producto_id=producto.id, tienda_id=tienda_id, cantidad=0)
        db.session.add(pres)
        db.session.commit()

    form = ProductoForm(obj=producto)

    if form.validate_on_submit():
        existe_otro = Producto.query.filter(
            Producto.nombre == form.nombre.data.strip(),
            Producto.id != producto.id
        ).first()
        if existe_otro:
            flash('Ya existe otro producto con ese nombre.', 'danger')
            return render_template('inventario/form.html', form=form, producto=producto)

        producto.nombre = form.nombre.data.strip()
        producto.codigo_barras = form.codigo_barras.data.strip() if form.codigo_barras.data else None
        producto.categoria = form.categoria.data or None

        pres.precio_proveedor = form.precio_proveedor.data or 0
        pres.precio_proveedor2 = form.precio_proveedor2.data or 0
        pres.precio_proveedor3 = form.precio_proveedor3.data or 0
        pres.porcentaje = form.porcentaje.data or 0
        pres.precio_venta = form.precio_venta.data or 0
        pres.condicion1 = form.condicion1.data or ''
        pres.precio_venta1 = form.precio_venta1.data or 0
        pres.condicion2 = form.condicion2.data or ''
        pres.precio_venta2 = form.precio_venta2.data or 0
        pres.condicion3 = form.condicion3.data or ''
        pres.precio_venta3 = form.precio_venta3.data or 0

        db.session.commit()
        flash(f'Producto "{producto.nombre}" actualizado.', 'success')
        return redirect(url_for('inventario.lista'))

    if request.method == 'GET':
        form.precio_proveedor.data = float(pres.precio_proveedor) if pres.precio_proveedor else 0
        form.precio_proveedor2.data = float(pres.precio_proveedor2) if pres.precio_proveedor2 else 0
        form.precio_proveedor3.data = float(pres.precio_proveedor3) if pres.precio_proveedor3 else 0
        form.porcentaje.data = float(pres.porcentaje) if pres.porcentaje else 0
        form.precio_venta.data = float(pres.precio_venta) if pres.precio_venta else 0
        form.condicion1.data = pres.condicion1 or ''
        form.precio_venta1.data = float(pres.precio_venta1) if pres.precio_venta1 else 0
        form.condicion2.data = pres.condicion2 or ''
        form.precio_venta2.data = float(pres.precio_venta2) if pres.precio_venta2 else 0
        form.condicion3.data = pres.condicion3 or ''
        form.precio_venta3.data = float(pres.precio_venta3) if pres.precio_venta3 else 0

    return render_template('inventario/form.html', form=form, producto=producto, presentacion=pres)


# ==================== ELIMINAR ====================
@bp.route('/<int:producto_id>/eliminar', methods=['POST'])
@login_required
@programador_requerido
def eliminar(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    nombre = producto.nombre
    db.session.delete(producto)
    db.session.commit()
    flash(f'Producto "{nombre}" eliminado.', 'success')
    return redirect(url_for('inventario.lista'))


# ==================== ACTUALIZAR STOCK INDIVIDUAL ====================
@bp.route('/<int:producto_id>/stock', methods=['POST'])
@login_required
@admin_requerido
def actualizar_stock(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    tienda_id = tienda_actual()
    cantidad = request.form.get('cantidad', type=int)

    if cantidad is None or cantidad < 0:
        flash('Cantidad inválida.', 'danger')
        return redirect(url_for('inventario.lista'))

    pres = ProductoTienda.query.filter_by(
        producto_id=producto_id, tienda_id=tienda_id
    ).first()

    if pres is None:
        pres = ProductoTienda(producto_id=producto_id, tienda_id=tienda_id, cantidad=0)
        db.session.add(pres)

    pres.cantidad = cantidad
    db.session.commit()
    flash(f'Stock de "{producto.nombre}" actualizado a {cantidad}.', 'success')
    return redirect(url_for('inventario.lista'))


# ==================== STOCK MASIVO (LISTA PARA EDITAR MUCHOS) ====================
@bp.route('/stock-masivo', methods=['GET', 'POST'])
@login_required
@admin_requerido
def stock_masivo():
    tienda_id = tienda_actual()
    if not tienda_id:
        flash('No hay tienda activa.', 'danger')
        return redirect(url_for('inventario.lista'))

    if request.method == 'POST':
        cambios = 0
        for key, value in request.form.items():
            if key.startswith('stock_'):
                try:
                    producto_id = int(key.replace('stock_', ''))
                    nueva_cant = int(value)
                    if nueva_cant < 0:
                        continue
                    pres = ProductoTienda.query.filter_by(
                        producto_id=producto_id, tienda_id=tienda_id
                    ).first()
                    if pres and pres.cantidad != nueva_cant:
                        pres.cantidad = nueva_cant
                        cambios += 1
                except (ValueError, TypeError):
                    continue
        db.session.commit()
        flash(f'{cambios} productos actualizados.', 'success')
        return redirect(url_for('inventario.stock_masivo',
                                q=request.args.get('q', ''),
                                filtro=request.args.get('filtro', '')))

    # GET: mostrar lista
    busqueda = request.args.get('q', '', type=str).strip()
    filtro = request.args.get('filtro', '', type=str).strip()  # '', 'sin_stock', 'bajo'
    page = request.args.get('page', 1, type=int)

    # Query con JOIN para traer producto + presentación
    q = db.session.query(Producto, ProductoTienda).join(
        ProductoTienda, Producto.id == ProductoTienda.producto_id
    ).filter(ProductoTienda.tienda_id == tienda_id)

    if busqueda:
        q = q.filter(or_(
            Producto.nombre.ilike(f'%{busqueda}%'),
            Producto.codigo_barras.ilike(f'%{busqueda}%')
        ))

    if filtro == 'sin_stock':
        q = q.filter(ProductoTienda.cantidad <= 0)
    elif filtro == 'bajo':
        q = q.filter(ProductoTienda.cantidad.between(1, 5))

    q = q.order_by(Producto.nombre)
    paginacion = q.paginate(page=page, per_page=50, error_out=False)

    tiendas = Tienda.query.filter_by(activa=True).all()

    return render_template(
        'inventario/stock_masivo.html',
        paginacion=paginacion,
        busqueda=busqueda,
        filtro=filtro,
        tienda_id=tienda_id,
        tiendas=tiendas,
    )


# ==================== API: BÚSQUEDA RÁPIDA (AJAX) ====================
@bp.route('/api/buscar')
@login_required
def api_buscar():
    q = request.args.get('q', '', type=str).strip()
    if len(q) < 2:
        return jsonify([])

    tienda_id = tienda_actual()
    productos = Producto.query.filter(
        or_(
            Producto.nombre.ilike(f'%{q}%'),
            Producto.codigo_barras.ilike(f'%{q}%')
        )
    ).limit(20).all()

    resultados = []
    for p in productos:
        pres = None
        if tienda_id:
            pres = ProductoTienda.query.filter_by(
                producto_id=p.id, tienda_id=tienda_id
            ).first()
        resultados.append({
            'id': p.id,
            'nombre': p.nombre,
            'codigo_barras': p.codigo_barras or '',
            'categoria': p.categoria or '',
            'stock': pres.cantidad if pres else 0,
            'precio_venta': float(pres.precio_venta) if pres and pres.precio_venta else 0,
        })

    return jsonify(resultados)
'''

# ==================== TEMPLATE: LISTA ACTUALIZADA CON FILTROS ====================
ARCHIVOS['app/templates/inventario/lista.html'] = '''{% extends 'base.html' %}
{% block titulo %}Inventario{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-box-seam"></i> Inventario
        {% if current_user.es_programador() and tiendas|length > 1 %}
            <small class="text-muted">- Viendo:
                <select id="selector-tienda" class="form-select form-select-sm d-inline-block" style="width:auto;">
                    {% for t in tiendas %}
                        <option value="{{ t.id }}" {% if t.id == tienda_id %}selected{% endif %}>{{ t.nombre }}</option>
                    {% endfor %}
                </select>
            </small>
        {% endif %}
    </h1>
    <div>
        {% if puede_editar %}
        <a href="{{ url_for('inventario.stock_masivo') }}" class="btn btn-success">
            <i class="bi bi-lightning"></i> Stock masivo
        </a>
        <a href="{{ url_for('inventario.nuevo') }}" class="btn btn-primary">
            <i class="bi bi-plus-circle"></i> Nuevo producto
        </a>
        {% endif %}
    </div>
</div>

<!-- Filtros -->
<div class="card mb-3">
    <div class="card-body py-2">
        <div class="row g-2 align-items-center">
            <div class="col-md-6">
                <form method="GET" class="input-group">
                    <span class="input-group-text"><i class="bi bi-search"></i></span>
                    <input type="text" name="q" class="form-control"
                           placeholder="Buscar por nombre o código..." value="{{ busqueda }}">
                    {% if filtro_stock %}<input type="hidden" name="filtro" value="{{ filtro_stock }}">{% endif %}
                    <button type="submit" class="btn btn-primary">Buscar</button>
                </form>
            </div>
            <div class="col-md-6 text-end">
                <div class="btn-group">
                    <a href="{{ url_for('inventario.lista', q=busqueda, tienda=tienda_id) }}"
                       class="btn btn-sm {% if not filtro_stock %}btn-primary{% else %}btn-outline-primary{% endif %}">
                        Todos ({{ contadores.total }})
                    </a>
                    <a href="{{ url_for('inventario.lista', q=busqueda, filtro='sin_stock', tienda=tienda_id) }}"
                       class="btn btn-sm {% if filtro_stock == 'sin_stock' %}btn-danger{% else %}btn-outline-danger{% endif %}">
                        🔴 Sin stock ({{ contadores.sin_stock }})
                    </a>
                    <a href="{{ url_for('inventario.lista', q=busqueda, filtro='bajo', tienda=tienda_id) }}"
                       class="btn btn-sm {% if filtro_stock == 'bajo' %}btn-warning{% else %}btn-outline-warning{% endif %}">
                        🟡 Bajo ({{ contadores.bajo }})
                    </a>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Tabla -->
<div class="card">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th style="width: 60px;">ID</th>
                    <th>Producto</th>
                    <th style="width: 120px;">Código</th>
                    <th style="width: 100px;" class="text-end">P. Venta</th>
                    <th style="width: 120px;" class="text-center">Stock</th>
                    <th style="width: 170px;" class="text-end">Acciones</th>
                </tr>
            </thead>
            <tbody>
                {% for item in productos %}
                    {% set p = item.producto %}
                    {% set pres = item.presentacion %}
                    {% set stock = item.stock %}
                    <tr>
                        <td class="text-muted small">{{ p.id }}</td>
                        <td>
                            <div class="fw-semibold">{{ p.nombre }}</div>
                            {% if p.categoria %}
                                <span class="badge bg-secondary-subtle text-secondary">{{ p.categoria }}</span>
                            {% endif %}
                        </td>
                        <td class="text-muted small">{{ p.codigo_barras or '-' }}</td>
                        <td class="text-end fw-semibold">
                            {% if pres %}
                                ${{ "{:,.0f}".format(item.precio_venta) }}
                            {% else %}
                                <span class="text-muted">-</span>
                            {% endif %}
                        </td>
                        <td class="text-center">
                            {% if stock == 0 %}
                                <span class="badge bg-danger">🔴 Agotado</span>
                            {% elif stock <= 5 %}
                                <span class="badge bg-warning text-dark">🟡 {{ stock }}</span>
                            {% else %}
                                <span class="badge bg-success">🟢 {{ stock }}</span>
                            {% endif %}
                        </td>
                        <td class="text-end">
                            {% if puede_editar %}
                                <button type="button" class="btn btn-sm btn-outline-success btn-stock"
                                        title="Actualizar stock" data-id="{{ p.id }}"
                                        data-nombre="{{ p.nombre }}" data-stock="{{ stock }}">
                                    <i class="bi bi-plus-slash-minus"></i>
                                </button>
                                <a href="{{ url_for('inventario.editar', producto_id=p.id) }}"
                                   class="btn btn-sm btn-outline-primary" title="Editar">
                                    <i class="bi bi-pencil"></i>
                                </a>
                            {% endif %}
                            {% if current_user.es_programador() %}
                                <form method="POST" action="{{ url_for('inventario.eliminar', producto_id=p.id) }}"
                                      class="d-inline"
                                      onsubmit="return confirm('¿Eliminar {{ p.nombre }}?');">
                                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                                    <button type="submit" class="btn btn-sm btn-outline-danger" title="Eliminar">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </form>
                            {% endif %}
                        </td>
                    </tr>
                {% else %}
                    <tr>
                        <td colspan="6" class="text-center py-5 text-muted">
                            <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                            No hay productos que mostrar.
                        </td>
                    </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- Paginación -->
{% if paginacion.pages > 1 %}
    <nav class="mt-3">
        <ul class="pagination justify-content-center">
            <li class="page-item {% if not paginacion.has_prev %}disabled{% endif %}">
                <a class="page-link" href="{{ url_for('inventario.lista', page=paginacion.prev_num, q=busqueda, filtro=filtro_stock, tienda=tienda_id) }}">&laquo;</a>
            </li>
            {% for num in paginacion.iter_pages(left_edge=1, left_current=2, right_current=2, right_edge=1) %}
                {% if num %}
                    <li class="page-item {% if num == paginacion.page %}active{% endif %}">
                        <a class="page-link" href="{{ url_for('inventario.lista', page=num, q=busqueda, filtro=filtro_stock, tienda=tienda_id) }}">{{ num }}</a>
                    </li>
                {% else %}
                    <li class="page-item disabled"><span class="page-link">…</span></li>
                {% endif %}
            {% endfor %}
            <li class="page-item {% if not paginacion.has_next %}disabled{% endif %}">
                <a class="page-link" href="{{ url_for('inventario.lista', page=paginacion.next_num, q=busqueda, filtro=filtro_stock, tienda=tienda_id) }}">&raquo;</a>
            </li>
        </ul>
        <p class="text-center text-muted small">
            Mostrando {{ productos|length }} de {{ paginacion.total }}
        </p>
    </nav>
{% endif %}

<!-- Modal de stock -->
<div class="modal fade" id="modalStock" tabindex="-1">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <form method="POST" id="form-stock" action="">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <div class="modal-header bg-success text-white">
                    <h5 class="modal-title"><i class="bi bi-plus-slash-minus"></i> Actualizar stock</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p><strong id="stock-nombre"></strong></p>
                    <label class="form-label">Cantidad</label>
                    <input type="number" name="cantidad" id="stock-cantidad" class="form-control form-control-lg" min="0" required>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                    <button type="submit" class="btn btn-success">Guardar</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
{% if current_user.es_programador() and tiendas|length > 1 %}
document.getElementById('selector-tienda').addEventListener('change', function() {
    const url = new URL(window.location.href);
    url.searchParams.set('tienda', this.value);
    url.searchParams.delete('page');
    window.location.href = url.toString();
});
{% endif %}

document.querySelectorAll('.btn-stock').forEach(function(btn) {
    btn.addEventListener('click', function() {
        const id = this.dataset.id;
        const nombre = this.dataset.nombre;
        const stock = this.dataset.stock;
        document.getElementById('form-stock').action = '/inventario/' + id + '/stock';
        document.getElementById('stock-nombre').textContent = nombre;
        document.getElementById('stock-cantidad').value = stock;
        new bootstrap.Modal(document.getElementById('modalStock')).show();
    });
});
</script>
{% endblock %}
'''

# ==================== TEMPLATE: STOCK MASIVO ====================
ARCHIVOS['app/templates/inventario/stock_masivo.html'] = '''{% extends 'base.html' %}
{% block titulo %}Stock masivo{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-lightning"></i> Stock masivo
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
    <a href="{{ url_for('inventario.lista') }}" class="btn btn-outline-secondary">
        <i class="bi bi-arrow-left"></i> Volver
    </a>
</div>

<div class="alert alert-info">
    <i class="bi bi-info-circle"></i>
    Edita las cantidades directamente y presiona <strong>Guardar todos los cambios</strong>.
    Solo se actualizan los que cambien.
</div>

<!-- Filtros -->
<div class="card mb-3">
    <div class="card-body py-2">
        <div class="row g-2 align-items-center">
            <div class="col-md-6">
                <form method="GET" class="input-group">
                    <span class="input-group-text"><i class="bi bi-search"></i></span>
                    <input type="text" name="q" class="form-control"
                           placeholder="Buscar..." value="{{ busqueda }}">
                    {% if filtro %}<input type="hidden" name="filtro" value="{{ filtro }}">{% endif %}
                    <button type="submit" class="btn btn-primary">Buscar</button>
                </form>
            </div>
            <div class="col-md-6 text-end">
                <div class="btn-group">
                    <a href="{{ url_for('inventario.stock_masivo', q=busqueda, tienda=tienda_id) }}"
                       class="btn btn-sm {% if not filtro %}btn-primary{% else %}btn-outline-primary{% endif %}">
                        Todos
                    </a>
                    <a href="{{ url_for('inventario.stock_masivo', q=busqueda, filtro='sin_stock', tienda=tienda_id) }}"
                       class="btn btn-sm {% if filtro == 'sin_stock' %}btn-danger{% else %}btn-outline-danger{% endif %}">
                        🔴 Sin stock
                    </a>
                    <a href="{{ url_for('inventario.stock_masivo', q=busqueda, filtro='bajo', tienda=tienda_id) }}"
                       class="btn btn-sm {% if filtro == 'bajo' %}btn-warning{% else %}btn-outline-warning{% endif %}">
                        🟡 Bajo
                    </a>
                </div>
            </div>
        </div>
    </div>
</div>

<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

    <div class="card">
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead class="table-light">
                    <tr>
                        <th style="width: 60px;">ID</th>
                        <th>Producto</th>
                        <th style="width: 100px;" class="text-end">P. Venta</th>
                        <th style="width: 150px;" class="text-center">Stock actual</th>
                    </tr>
                </thead>
                <tbody>
                    {% for p, pres in paginacion.items %}
                    <tr>
                        <td class="text-muted small">{{ p.id }}</td>
                        <td>
                            <div class="fw-semibold">{{ p.nombre }}</div>
                            {% if p.codigo_barras %}
                            <small class="text-muted">{{ p.codigo_barras }}</small>
                            {% endif %}
                        </td>
                        <td class="text-end">${{ "{:,.0f}".format(pres.precio_venta or 0) }}</td>
                        <td>
                            <input type="number" name="stock_{{ p.id }}" class="form-control text-center"
                                   value="{{ pres.cantidad }}" min="0">
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="4" class="text-center py-5 text-muted">
                            <i class="bi bi-inbox fs-1 d-block mb-2"></i>
                            No hay productos que mostrar.
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Barra de guardar fija -->
    <div class="position-sticky bottom-0 mt-3 p-3 bg-white border-top shadow-sm">
        <div class="d-flex justify-content-between align-items-center">
            <div class="text-muted small">
                Mostrando {{ paginacion.items|length }} de {{ paginacion.total }}
            </div>
            <button type="submit" class="btn btn-success btn-lg">
                <i class="bi bi-save"></i> Guardar todos los cambios
            </button>
        </div>
    </div>
</form>

<!-- Paginación -->
{% if paginacion.pages > 1 %}
    <nav class="mt-3">
        <ul class="pagination justify-content-center">
            <li class="page-item {% if not paginacion.has_prev %}disabled{% endif %}">
                <a class="page-link" href="{{ url_for('inventario.stock_masivo', page=paginacion.prev_num, q=busqueda, filtro=filtro, tienda=tienda_id) }}">&laquo;</a>
            </li>
            {% for num in paginacion.iter_pages(left_edge=1, left_current=2, right_current=2, right_edge=1) %}
                {% if num %}
                    <li class="page-item {% if num == paginacion.page %}active{% endif %}">
                        <a class="page-link" href="{{ url_for('inventario.stock_masivo', page=num, q=busqueda, filtro=filtro, tienda=tienda_id) }}">{{ num }}</a>
                    </li>
                {% else %}
                    <li class="page-item disabled"><span class="page-link">…</span></li>
                {% endif %}
            {% endfor %}
            <li class="page-item {% if not paginacion.has_next %}disabled{% endif %}">
                <a class="page-link" href="{{ url_for('inventario.stock_masivo', page=paginacion.next_num, q=busqueda, filtro=filtro, tienda=tienda_id) }}">&raquo;</a>
            </li>
        </ul>
    </nav>
{% endif %}

<script>
const selectorTienda = document.getElementById('selector-tienda');
if (selectorTienda) {
    selectorTienda.addEventListener('change', function() {
        const url = new URL(window.location.href);
        url.searchParams.set('tienda', this.value);
        url.searchParams.delete('page');
        window.location.href = url.toString();
    });
}
</script>
{% endblock %}
'''


def main():
    print(f'Aplicando cambios en: {RAIZ}')
    print('-' * 60)
    for rel_path, contenido in ARCHIVOS.items():
        ruta = os.path.join(RAIZ, *rel_path.split('/'))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f'  OK  {rel_path}')
    print('-' * 60)
    print(f'Listo: {len(ARCHIVOS)} archivos actualizados.')


if __name__ == '__main__':
    main()