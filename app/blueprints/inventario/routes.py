# app/blueprints/inventario/routes.py
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
