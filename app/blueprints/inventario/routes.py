import uuid
# app/blueprints/inventario/routes.py
from flask import render_template, redirect, url_for, flash, request, jsonify, abort, current_app
from datetime import datetime
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from . import bp
from .forms import ProductoForm, StockForm
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from app.models.tienda import Tienda
from app.utils.decorators import admin_requerido, programador_requerido


def es_central():
    """v2.23: True si esta instancia corre en el servidor central."""
    return current_app.config.get('MODO', 'tienda_local') == 'central'


def tienda_actual():
    # v2.23-selector-admin-solo-central:
    # Solo admin/programador EN CENTRAL puede cambiar de tienda.
    # En tiendas, siempre la tienda del usuario (o primera si programador local).
    if es_central() and (current_user.es_programador() or current_user.es_admin()):
        tid = request.args.get('tienda', type=int)
        if tid:
            return tid
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None
    if current_user.es_programador():
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None
    return current_user.tienda_id


def puede_editar():
    return current_user.es_admin()


def _audit(accion, detalle, tienda_id=None):
    try:
        from app.services.auditoria_service import registrar_auditoria
        registrar_auditoria(accion, detalle, tienda_id=tienda_id)
    except Exception as e:
        print(f'[auditoria {accion}] aviso: {e}')


# ==================== LISTA ====================
@bp.route('/')
@login_required
def lista():
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '', type=str).strip()
    filtro_stock = request.args.get('filtro', '', type=str).strip()
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

    if filtro_stock and tienda_id:
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
        modo_central=es_central(),
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

        # v2.16-validar-codigo: el codigo de barras debe ser unico
        codigo_nuevo = form.codigo_barras.data.strip() if form.codigo_barras.data else None
        if codigo_nuevo:
            existe_codigo = Producto.query.filter_by(codigo_barras=codigo_nuevo).first()
            if existe_codigo:
                flash(f'Ya existe un producto con el codigo "{codigo_nuevo}": {existe_codigo.nombre}', 'danger')
                return render_template('inventario/form.html', form=form, producto=None)

        producto = Producto(
            nombre=form.nombre.data.strip(),
            codigo_barras=form.codigo_barras.data.strip() if form.codigo_barras.data else None,
            categoria=form.categoria.data or None,
            codigo_global=str(uuid.uuid4()),
            modificado_por_nombre=current_user.nombre,
            modificado_en=datetime.utcnow(),
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

        _audit(
            'producto_crear',
            f'{producto.nombre} (ID {producto.id}) | Precio venta: ${float(form.precio_venta.data or 0):,.0f}'
        )

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

        # v2.16-validar-codigo: el codigo de barras debe ser unico (excepto el propio)
        codigo_nuevo = form.codigo_barras.data.strip() if form.codigo_barras.data else None
        if codigo_nuevo:
            existe_codigo = Producto.query.filter(
                Producto.codigo_barras == codigo_nuevo,
                Producto.id != producto.id
            ).first()
            if existe_codigo:
                flash(f'Ya existe otro producto con el codigo "{codigo_nuevo}": {existe_codigo.nombre}', 'danger')
                return render_template('inventario/form.html', form=form, producto=producto)

        viejo_nombre = producto.nombre
        viejo_precio = float(pres.precio_venta or 0)
        viejo_prov = float(pres.precio_proveedor or 0)

        nuevo_nombre = form.nombre.data.strip()

        producto.nombre = nuevo_nombre
        producto.codigo_barras = form.codigo_barras.data.strip() if form.codigo_barras.data else None
        producto.categoria = form.categoria.data or None
        producto.modificado_por_nombre = current_user.nombre
        producto.modificado_en = datetime.utcnow()

        # v2.62-fix-rename-historico: actualizar nombre en ventas viejas
        if viejo_nombre != nuevo_nombre:
            n_actualizadas = (DetalleFactura.query
                              .filter_by(producto_id=producto.id,
                                         producto_nombre=viejo_nombre)
                              .update({'producto_nombre': nuevo_nombre},
                                      synchronize_session=False))
            if n_actualizadas > 0:
                print(f'[editar] Histórico actualizado: {n_actualizadas} filas '
                      f'"{viejo_nombre}" -> "{nuevo_nombre}"')

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

        # v2.22-fix-marcar-todas-tiendas: si es admin en Central, marcar TODAS
        # las tiendas activas. Si es operario, solo su tienda.
        if current_user.es_admin() or current_user.es_programador():
            tiendas_activas = Tienda.query.filter_by(activa=True).all()
            for t in tiendas_activas:
                p_t = ProductoTienda.query.filter_by(
                    producto_id=producto.id, tienda_id=t.id
                ).first()
                if not p_t:
                    p_t = ProductoTienda(
                        producto_id=producto.id, tienda_id=t.id, cantidad=0
                    )
                    db.session.add(p_t)
                p_t.sync_estado = 'pendiente'
                p_t.sync_fecha = datetime.utcnow()
        else:
            pres.sync_estado = 'pendiente'
            pres.sync_fecha = datetime.utcnow()

        db.session.commit()

        cambios = []
        if viejo_nombre != producto.nombre:
            cambios.append(f'nombre: "{viejo_nombre}" -> "{producto.nombre}"')
        nuevo_precio = float(pres.precio_venta or 0)
        if viejo_precio != nuevo_precio:
            cambios.append(f'precio: ${viejo_precio:,.0f} -> ${nuevo_precio:,.0f}')
        nuevo_prov = float(pres.precio_proveedor or 0)
        if viejo_prov != nuevo_prov:
            cambios.append(f'costo: ${viejo_prov:,.0f} -> ${nuevo_prov:,.0f}')

        detalle = f'{producto.nombre} (ID {producto.id}, tienda {tienda_id})'
        if cambios:
            detalle += ' | ' + ' | '.join(cambios)
        else:
            detalle += ' (sin cambios significativos)'

        _audit('producto_editar', detalle, tienda_id=tienda_id)

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
    pid = producto.id

    # v2.62-fix-no-borrar: bloquear borrado si tiene facturas asociadas
    # (evita que el ID se reutilice y corrompa históricos)
    tiene_facturas = DetalleFactura.query.filter_by(producto_id=pid).first()
    if tiene_facturas:
        flash(
            f'No se puede eliminar "{nombre}": tiene ventas asociadas. '
            f'Si ya no lo vendés, cambialo de categoría o dejaló inactivo.',
            'danger'
        )
        return redirect(url_for('inventario.lista'))

    db.session.delete(producto)
    db.session.commit()

    _audit('producto_eliminar', f'{nombre} (ID {pid})')

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

    cantidad_vieja = pres.cantidad
    pres.cantidad = cantidad
    pres.sync_estado = 'pendiente'
    pres.sync_fecha = datetime.utcnow()
    db.session.commit()

    _audit(
        'producto_stock',
        f'{producto.nombre} (ID {producto.id}, tienda {tienda_id}) | Stock: {cantidad_vieja} -> {cantidad}',
        tienda_id=tienda_id,
    )

    flash(f'Stock de "{producto.nombre}" actualizado a {cantidad}.', 'success')
    return redirect(url_for('inventario.lista'))


# ==================== STOCK MASIVO ====================
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
        cambios_detalle = []
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
                        producto = Producto.query.get(producto_id)
                        if producto:
                            cambios_detalle.append(
                                f'{producto.nombre}: {pres.cantidad} -> {nueva_cant}'
                            )
                        pres.cantidad = nueva_cant
                        pres.sync_estado = 'pendiente'
                        pres.sync_fecha = datetime.utcnow()
                        cambios += 1
                except (ValueError, TypeError):
                    continue
        db.session.commit()

        if cambios > 0:
            _audit(
                'producto_stock_masivo',
                f'{cambios} productos actualizados en tienda {tienda_id} | ' +
                '; '.join(cambios_detalle[:10]) +
                (f' ... (+{len(cambios_detalle)-10} más)' if len(cambios_detalle) > 10 else ''),
                tienda_id=tienda_id,
            )

        flash(f'{cambios} productos actualizados.', 'success')
        return redirect(url_for('inventario.stock_masivo',
                                q=request.args.get('q', ''),
                                filtro=request.args.get('filtro', '')))

    busqueda = request.args.get('q', '', type=str).strip()
    filtro = request.args.get('filtro', '', type=str).strip()
    page = request.args.get('page', 1, type=int)

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


# ==================== API: BÚSQUEDA RÁPIDA ====================
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