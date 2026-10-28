# scripts/crear_inventario.py
# Crea el módulo de inventario (blueprint + forms + routes + templates).
# Ejecutar UNA VEZ: python scripts\crear_inventario.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== BLUEPRINT ====================
ARCHIVOS['app/blueprints/inventario/__init__.py'] = '''# app/blueprints/inventario/__init__.py
from flask import Blueprint

bp = Blueprint('inventario', __name__, url_prefix='/inventario')

from . import routes  # noqa: E402, F401
'''

# ==================== FORMS ====================
ARCHIVOS['app/blueprints/inventario/forms.py'] = '''# app/blueprints/inventario/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ProductoForm(FlaskForm):
    # ---------- Datos básicos ----------
    nombre = StringField(
        'Nombre del producto',
        validators=[DataRequired(message='El nombre es obligatorio'), Length(max=200)]
    )
    codigo_barras = StringField(
        'Código de barras',
        validators=[Optional(), Length(max=50)]
    )
    categoria = SelectField(
        'Categoría',
        choices=[
            ('', '-- Sin categoría --'),
            ('dulce', 'Dulce'),
            ('cigarro', 'Cigarrillo'),
            ('bebida', 'Bebida'),
            ('snack', 'Snack / Mecato'),
            ('aseo', 'Aseo'),
            ('licor', 'Licor'),
            ('otro', 'Otro'),
        ],
        validators=[Optional()]
    )

    # ---------- Precios de proveedor ----------
    precio_proveedor = DecimalField(
        'Precio proveedor 1',
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        default=0
    )
    precio_proveedor2 = DecimalField(
        'Precio proveedor 2',
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        default=0
    )
    precio_proveedor3 = DecimalField(
        'Precio proveedor 3',
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        default=0
    )

    # ---------- Precio venta ----------
    porcentaje = DecimalField(
        '% Ganancia',
        validators=[Optional(), NumberRange(min=0, max=500)],
        places=2,
        default=0
    )
    precio_venta = DecimalField(
        'Precio venta base',
        validators=[DataRequired(message='El precio de venta es obligatorio'), NumberRange(min=0)],
        places=2
    )

    # ---------- Descuentos por cantidad ----------
    condicion1 = StringField('Cantidad mínima 1', validators=[Optional(), Length(max=10)])
    precio_venta1 = DecimalField('Precio unitario 1', validators=[Optional(), NumberRange(min=0)], places=2, default=0)

    condicion2 = StringField('Cantidad mínima 2', validators=[Optional(), Length(max=10)])
    precio_venta2 = DecimalField('Precio unitario 2', validators=[Optional(), NumberRange(min=0)], places=2, default=0)

    condicion3 = StringField('Cantidad mínima 3', validators=[Optional(), Length(max=10)])
    precio_venta3 = DecimalField('Precio unitario 3', validators=[Optional(), NumberRange(min=0)], places=2, default=0)

    submit = SubmitField('Guardar')


class StockForm(FlaskForm):
    """Solo para editar el stock de una tienda específica."""
    cantidad = IntegerField(
        'Cantidad en stock',
        validators=[DataRequired(), NumberRange(min=0)]
    )
    submit = SubmitField('Actualizar stock')
'''

# ==================== ROUTES ====================
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


# ==================== HELPERS ====================
def tienda_actual():
    """Devuelve el tienda_id que el usuario está manejando actualmente."""
    if current_user.es_programador():
        # Programador puede ver cualquier tienda (query param ?tienda=X)
        tid = request.args.get('tienda', type=int)
        if tid:
            return tid
        # Si no especifica, ve la primera tienda
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None
    return current_user.tienda_id


def puede_editar():
    """Solo admin y programador pueden editar productos."""
    return current_user.es_admin()


# ==================== LISTA ====================
@bp.route('/')
@login_required
def lista():
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '', type=str).strip()
    tienda_id = tienda_actual()
    per_page = 20

    # Query base: productos + su presentación en la tienda actual
    query = Producto.query

    if busqueda:
        query = query.filter(
            or_(
                Producto.nombre.ilike(f'%{busqueda}%'),
                Producto.codigo_barras.ilike(f'%{busqueda}%')
            )
        )

    query = query.order_by(Producto.nombre)
    paginacion = query.paginate(page=page, per_page=per_page, error_out=False)

    # Preparar datos de presentación (precio + stock) para la tienda actual
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

    return render_template(
        'inventario/lista.html',
        productos=productos_con_info,
        paginacion=paginacion,
        busqueda=busqueda,
        tienda_id=tienda_id,
        tiendas=tiendas,
        puede_editar=puede_editar(),
    )


# ==================== CREAR ====================
@bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@admin_requerido
def nuevo():
    form = ProductoForm()
    if form.validate_on_submit():
        # Verificar duplicado
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
        db.session.flush()  # para obtener el id

        # Crear presentación en TODAS las tiendas activas (con la misma config)
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
        # Verificar que el nombre no choque con otro producto
        existe_otro = Producto.query.filter(
            Producto.nombre == form.nombre.data.strip(),
            Producto.id != producto.id
        ).first()
        if existe_otro:
            flash('Ya existe otro producto con ese nombre.', 'danger')
            return render_template('inventario/form.html', form=form, producto=producto)

        # Actualizar datos globales
        producto.nombre = form.nombre.data.strip()
        producto.codigo_barras = form.codigo_barras.data.strip() if form.codigo_barras.data else None
        producto.categoria = form.categoria.data or None

        # Actualizar precios de la tienda actual
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

    # Pre-cargar datos de la presentación actual
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

    return render_template(
        'inventario/form.html',
        form=form,
        producto=producto,
        presentacion=pres,
    )


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


# ==================== ACTUALIZAR STOCK ====================
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


# ==================== API: BÚSQUEDA RÁPIDA (AJAX) ====================
@bp.route('/api/buscar')
@login_required
def api_buscar():
    """Búsqueda rápida para autocompletado."""
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

# ==================== TEMPLATES ====================
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
    {% if puede_editar %}
        <a href="{{ url_for('inventario.nuevo') }}" class="btn btn-primary">
            <i class="bi bi-plus-circle"></i> Nuevo producto
        </a>
    {% endif %}
</div>

<!-- Barra de búsqueda -->
<div class="card mb-3">
    <div class="card-body py-2">
        <form method="GET" class="row g-2 align-items-center">
            <div class="col-md-8">
                <div class="input-group">
                    <span class="input-group-text"><i class="bi bi-search"></i></span>
                    <input type="text" name="q" class="form-control" 
                           placeholder="Buscar por nombre o código de barras..." 
                           value="{{ busqueda }}" autofocus>
                    {% if busqueda %}
                        <a href="{{ url_for('inventario.lista') }}" class="btn btn-outline-secondary">
                            <i class="bi bi-x"></i> Limpiar
                        </a>
                    {% endif %}
                    <button type="submit" class="btn btn-primary">Buscar</button>
                </div>
            </div>
            <div class="col-md-4 text-end">
                <span class="text-muted small">
                    {{ paginacion.total }} producto{{ 's' if paginacion.total != 1 }}
                </span>
            </div>
        </form>
    </div>
</div>

<!-- Tabla de productos -->
<div class="card">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th style="width: 60px;">ID</th>
                    <th>Producto</th>
                    <th style="width: 120px;">Código</th>
                    <th style="width: 100px;" class="text-end">P. Venta</th>
                    <th style="width: 100px;" class="text-center">Stock</th>
                    <th style="width: 150px;" class="text-end">Acciones</th>
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
                                <a href="{{ url_for('inventario.editar', producto_id=p.id) }}" 
                                   class="btn btn-sm btn-outline-primary" title="Editar">
                                    <i class="bi bi-pencil"></i>
                                </a>
                            {% endif %}
                            {% if current_user.es_programador() %}
                                <form method="POST" 
                                      action="{{ url_for('inventario.eliminar', producto_id=p.id) }}"
                                      class="d-inline"
                                      onsubmit="return confirm('¿Eliminar {{ p.nombre }}? Esta acción es irreversible.');">
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
                            {% if busqueda %}
                                No hay productos que coincidan con "{{ busqueda }}".
                            {% else %}
                                No hay productos todavía. {% if puede_editar %}Crea el primero con el botón "Nuevo producto".{% endif %}
                            {% endif %}
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
                <a class="page-link" href="{{ url_for('inventario.lista', page=paginacion.prev_num, q=busqueda, tienda=tienda_id) }}">
                    &laquo; Anterior
                </a>
            </li>
            {% for num in paginacion.iter_pages(left_edge=1, left_current=2, right_current=2, right_edge=1) %}
                {% if num %}
                    <li class="page-item {% if num == paginacion.page %}active{% endif %}">
                        <a class="page-link" href="{{ url_for('inventario.lista', page=num, q=busqueda, tienda=tienda_id) }}">{{ num }}</a>
                    </li>
                {% else %}
                    <li class="page-item disabled"><span class="page-link">…</span></li>
                {% endif %}
            {% endfor %}
            <li class="page-item {% if not paginacion.has_next %}disabled{% endif %}">
                <a class="page-link" href="{{ url_for('inventario.lista', page=paginacion.next_num, q=busqueda, tienda=tienda_id) }}">
                    Siguiente &raquo;
                </a>
            </li>
        </ul>
        <p class="text-center text-muted small">
            Mostrando {{ productos|length }} de {{ paginacion.total }} productos 
            (página {{ paginacion.page }} de {{ paginacion.pages }})
        </p>
    </nav>
{% endif %}

{% if current_user.es_programador() and tiendas|length > 1 %}
<script>
    document.getElementById('selector-tienda').addEventListener('change', function() {
        const url = new URL(window.location.href);
        url.searchParams.set('tienda', this.value);
        url.searchParams.delete('page');
        window.location.href = url.toString();
    });
</script>
{% endif %}
{% endblock %}
'''

ARCHIVOS['app/templates/inventario/form.html'] = '''{% extends 'base.html' %}
{% block titulo %}{{ 'Editar' if producto else 'Nuevo' }} Producto{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-{{ 'pencil' if producto else 'plus-circle' }}"></i>
        {{ 'Editar producto' if producto else 'Nuevo producto' }}
    </h1>
    <a href="{{ url_for('inventario.lista') }}" class="btn btn-outline-secondary">
        <i class="bi bi-arrow-left"></i> Volver
    </a>
</div>

<form method="POST" novalidate>
    {{ form.hidden_tag() }}

    <div class="row g-3">
        <!-- ==================== COLUMNA IZQUIERDA ==================== -->
        <div class="col-lg-7">

            <!-- Datos básicos -->
            <div class="card mb-3">
                <div class="card-header bg-white fw-semibold">
                    <i class="bi bi-info-circle"></i> Datos básicos
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        {{ form.nombre.label(class="form-label") }}
                        {{ form.nombre(class="form-control" + (" is-invalid" if form.nombre.errors else ""), placeholder="Ej: Coca-Cola 400ml") }}
                        {% for error in form.nombre.errors %}
                            <div class="invalid-feedback">{{ error }}</div>
                        {% endfor %}
                    </div>

                    <div class="row">
                        <div class="col-md-6 mb-3">
                            {{ form.codigo_barras.label(class="form-label") }}
                            {{ form.codigo_barras(class="form-control", placeholder="Opcional") }}
                        </div>
                        <div class="col-md-6 mb-3">
                            {{ form.categoria.label(class="form-label") }}
                            {{ form.categoria(class="form-select") }}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Precios por cantidad -->
            <div class="card mb-3">
                <div class="card-header bg-white fw-semibold">
                    <i class="bi bi-tags"></i> Precios por cantidad (opcional)
                </div>
                <div class="card-body">
                    <p class="text-muted small mb-3">
                        Si el cliente compra una cantidad mayor o igual a la indicada, se aplica el precio especial.
                    </p>

                    <!-- Condición 1 -->
                    <div class="row g-2 mb-2">
                        <div class="col-md-4">
                            {{ form.condicion1(class="form-control", placeholder="Ej: 3") }}
                        </div>
                        <div class="col-md-8">
                            <div class="input-group">
                                <span class="input-group-text">$</span>
                                {{ form.precio_venta1(class="form-control") }}
                            </div>
                        </div>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-md-4"><small class="text-muted">Cant. mínima 1</small></div>
                        <div class="col-md-8"><small class="text-muted">Precio unitario con descuento 1</small></div>
                    </div>

                    <!-- Condición 2 -->
                    <div class="row g-2 mb-2">
                        <div class="col-md-4">
                            {{ form.condicion2(class="form-control", placeholder="Ej: 6") }}
                        </div>
                        <div class="col-md-8">
                            <div class="input-group">
                                <span class="input-group-text">$</span>
                                {{ form.precio_venta2(class="form-control") }}
                            </div>
                        </div>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-md-4"><small class="text-muted">Cant. mínima 2</small></div>
                        <div class="col-md-8"><small class="text-muted">Precio unitario con descuento 2</small></div>
                    </div>

                    <!-- Condición 3 -->
                    <div class="row g-2 mb-2">
                        <div class="col-md-4">
                            {{ form.condicion3(class="form-control", placeholder="Ej: 12") }}
                        </div>
                        <div class="col-md-8">
                            <div class="input-group">
                                <span class="input-group-text">$</span>
                                {{ form.precio_venta3(class="form-control") }}
                            </div>
                        </div>
                    </div>
                    <div class="row g-2">
                        <div class="col-md-4"><small class="text-muted">Cant. mínima 3</small></div>
                        <div class="col-md-8"><small class="text-muted">Precio unitario con descuento 3</small></div>
                    </div>
                </div>
            </div>

        </div>

        <!-- ==================== COLUMNA DERECHA ==================== -->
        <div class="col-lg-5">

            <!-- Precios de proveedor -->
            <div class="card mb-3">
                <div class="card-header bg-white fw-semibold">
                    <i class="bi bi-truck"></i> Precios de proveedor
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        {{ form.precio_proveedor.label(class="form-label") }}
                        <div class="input-group">
                            <span class="input-group-text">$</span>
                            {{ form.precio_proveedor(class="form-control", placeholder="0") }}
                        </div>
                    </div>
                    <div class="mb-3">
                        {{ form.precio_proveedor2.label(class="form-label") }}
                        <div class="input-group">
                            <span class="input-group-text">$</span>
                            {{ form.precio_proveedor2(class="form-control", placeholder="0") }}
                        </div>
                    </div>
                    <div class="mb-3">
                        {{ form.precio_proveedor3.label(class="form-label") }}
                        <div class="input-group">
                            <span class="input-group-text">$</span>
                            {{ form.precio_proveedor3(class="form-control", placeholder="0") }}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Precio de venta -->
            <div class="card mb-3 border-primary">
                <div class="card-header bg-primary text-white fw-semibold">
                    <i class="bi bi-cash-coin"></i> Precio de venta
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        {{ form.precio_venta.label(class="form-label fw-bold") }}
                        <div class="input-group input-group-lg">
                            <span class="input-group-text">$</span>
                            {{ form.precio_venta(class="form-control" + (" is-invalid" if form.precio_venta.errors else ""), placeholder="0") }}
                            {% for error in form.precio_venta.errors %}
                                <div class="invalid-feedback">{{ error }}</div>
                            {% endfor %}
                        </div>
                    </div>
                    <div class="mb-0">
                        {{ form.porcentaje.label(class="form-label") }}
                        <div class="input-group">
                            {{ form.porcentaje(class="form-control", placeholder="0") }}
                            <span class="input-group-text">%</span>
                        </div>
                        <small class="text-muted">% de ganancia sobre el costo promedio</small>
                    </div>
                </div>
            </div>

            <!-- Botones -->
            <div class="d-grid gap-2">
                {{ form.submit(class="btn btn-primary btn-lg") }}
                <a href="{{ url_for('inventario.lista') }}" class="btn btn-outline-secondary">
                    Cancelar
                </a>
            </div>

        </div>
    </div>
</form>
{% endblock %}
'''

# ==================== REGISTRAR EN APP ====================
ARCHIVOS['app/blueprints/__init__.py'] = '''# app/blueprints/__init__.py
# Registro central de blueprints (opcional; se hace en app/__init__.py)
'''


def main():
    print(f'Creando modulo de inventario en: {RAIZ}')
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