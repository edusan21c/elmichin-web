import re

archivo = r'C:\michin_web\app\blueprints\inventario\routes.py'
with open(archivo, 'r', encoding='utf-8') as f:
    contenido = f.read()

nueva_funcion = '''# ==================== EDITAR ====================
@bp.route('/<int:producto_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_requerido
def editar(producto_id):
    producto = Producto.query.get_or_404(producto_id)

    tienda_id = tienda_actual() or 1
    tienda_actual_obj = Tienda.query.get(tienda_id)

    pres = ProductoTienda.query.filter_by(producto_id=producto.id, tienda_id=tienda_id).first()
    if pres is None:
        pres = ProductoTienda(producto_id=producto.id, tienda_id=tienda_id, cantidad=0)
        db.session.add(pres)
        db.session.commit()

    form = ProductoForm(obj=producto)

    if form.validate_on_submit():
        existe_otro = Producto.query.filter(Producto.categoria != 'INACTIVO').filter(Producto.nombre == form.nombre.data.strip(), Producto.id != producto.id).first()
        if existe_otro:
            flash('Ya existe otro producto con ese nombre.', 'danger')
            return render_template('inventario/form.html', form=form, producto=producto, presentacion=pres, tienda_actual_obj=tienda_actual_obj)

        codigo_nuevo = form.codigo_barras.data.strip() if form.codigo_barras.data else None
        if codigo_nuevo:
            existe_codigo = Producto.query.filter(Producto.categoria != 'INACTIVO').filter(Producto.codigo_barras == codigo_nuevo, Producto.id != producto.id).first()
            if existe_codigo:
                flash(f'Ya existe otro producto con el codigo "{codigo_nuevo}": {existe_codigo.nombre}', 'danger')
                return render_template('inventario/form.html', form=form, producto=producto, presentacion=pres, tienda_actual_obj=tienda_actual_obj)

        viejo_nombre = producto.nombre
        producto.nombre = form.nombre.data.strip()
        producto.codigo_barras = form.codigo_barras.data.strip() if form.codigo_barras.data else None
        producto.categoria = form.categoria.data or None
        producto.modificado_por_nombre = current_user.nombre
        producto.modificado_en = datetime.utcnow()

        if viejo_nombre != producto.nombre:
            DetalleFactura.query.filter_by(producto_id=producto.id, producto_nombre=viejo_nombre).update({'producto_nombre': producto.nombre}, synchronize_session=False)

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

        pres.sync_estado = 'pendiente'
        pres.sync_fecha = datetime.utcnow()

        if viejo_nombre != producto.nombre:
            for t in Tienda.query.filter_by(activa=True).all():
                p_t = ProductoTienda.query.filter_by(producto_id=producto.id, tienda_id=t.id).first()
                if p_t:
                    p_t.sync_estado = 'pendiente'
                    p_t.sync_fecha = datetime.utcnow()

        db.session.commit()

        _audit('producto_editar', f'{producto.nombre} (ID {producto.id}, tienda {tienda_id})', tienda_id=tienda_id)
        flash(f'Producto "{producto.nombre}" actualizado para {tienda_actual_obj.nombre if tienda_actual_obj else "la tienda"}.', 'success')
        return redirect(url_for('inventario.lista', tienda=tienda_id))

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

    return render_template('inventario/form.html', form=form, producto=producto, presentacion=pres, tienda_actual_obj=tienda_actual_obj)


# ==================== ELIMINAR ===================='''

# Reemplaza toda la función editar desde el inicio hasta ELIMINAR
patron = r"# ==================== EDITAR ====================.*?(?=# ==================== ELIMINAR)"
contenido = re.sub(patron, nueva_funcion, contenido, flags=re.DOTALL)

with open(archivo, 'w', encoding='utf-8') as f:
    f.write(contenido)

print("OK: Se reemplazo la funcion editar por completo de forma segura.")