import uuid
import os
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
from app.models.configuracion import Configuracion
from app.services import impresion_service
from app.utils.decorators import admin_requerido, programador_requerido

def es_central():
    return current_app.config.get('MODO', 'tienda_local') == 'central'

def tienda_actual():
    from flask import session, current_app
    from app.models.tienda import Tienda

    if current_app.config.get('MODO') == 'central' and (current_user.es_programador() or current_user.es_admin()):
        tid = request.args.get('tienda', type=int)
        if tid:
            session['tienda_actual_id'] = tid
            return tid
        if session.get('tienda_actual_id'):
            return session.get('tienda_actual_id')
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None

    if current_user.tienda_id:
        return current_user.tienda_id

    return current_app.config.get('TIENDA_ID')

def puede_editar():
    return current_user.es_admin()

def _audit(accion, detalle, tienda_id=None):
    try:
        from app.services.auditoria_service import registrar_auditoria
        registrar_auditoria(accion, detalle, tienda_id=tienda_id)
    except Exception as e:
        print(f'[auditoria {accion}] aviso: {e}')


# ==================== LISTA / SUGERIDO DE COMPRAS ====================
@bp.route('/')
@login_required
def lista():
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '', type=str).strip()
    filtro_stock = request.args.get('filtro', '', type=str).strip()
    tienda_id = tienda_actual()
    per_page = 50 # Aumentamos a 50 para la vista de compras

    # FILTRO DE INACTIVOS APLICADO AQUI
    query = Producto.query.filter(func.coalesce(Producto.categoria, '') != 'INACTIVO')

    if busqueda:
        query = query.filter(or_(
            Producto.nombre.ilike(f'%{busqueda}%'),
            Producto.codigo_barras.ilike(f'%{busqueda}%')
        ))
        
    # LÓGICA DEL SUGERIDO: Solo mostramos los que están en o por debajo del mínimo
    if tienda_id:
        query = query.join(ProductoTienda).filter(
            ProductoTienda.tienda_id == tienda_id,
            ProductoTienda.cantidad <= ProductoTienda.stock_minimo
        )

    query = query.order_by(Producto.nombre)
    paginacion = query.paginate(page=page, per_page=per_page, error_out=False)

    productos_con_info = []
    for prod in paginacion.items:
        pres = None
        if tienda_id:
            pres = ProductoTienda.query.filter_by(
                producto_id=prod.id, tienda_id=tienda_id
            ).first()
            
        stock_actual = pres.cantidad if pres and pres.cantidad is not None else 0
        stock_min = pres.stock_minimo if pres and pres.stock_minimo is not None else 5
        stock_max = pres.stock_maximo if pres and pres.stock_maximo is not None else 20
        
        # Calcular cantidad sugerida para volver al máximo
        sugerido = stock_max - stock_actual if stock_max > stock_actual else 0

        productos_con_info.append({
            'producto': prod,
            'presentacion': pres,
            'stock': stock_actual,
            'stock_minimo': stock_min,
            'stock_maximo': stock_max,
            'cantidad_sugerida': sugerido,
            'precio_venta': float(pres.precio_venta) if pres and pres.precio_venta else 0,
        })

    tiendas = Tienda.query.filter_by(activa=True).all()
    tienda_actual_obj = Tienda.query.get(tienda_id) if tienda_id else None

    return render_template('inventario/lista.html',
                           paginacion=paginacion,
                           productos=productos_con_info,
                           busqueda=busqueda,
                           tienda_id=tienda_id,
                           tiendas=tiendas,
                           tienda_actual_obj=tienda_actual_obj,
                           filtro_stock='sugerido')


# ==================== IMPRESIÓN DE ORDEN DE COMPRA ====================
@bp.route('/imprimir-orden', methods=['POST'])
@login_required
def imprimir_orden():
    data = request.json
    texto = data.get('texto', '')
    tienda_id = data.get('tienda_id')

    # Buscar la IP o el USB según la configuración de esa tienda
    conf_ip = Configuracion.query.filter_by(clave='impresora_ip', tienda_id=tienda_id).first()
    conf_puerto = Configuracion.query.filter_by(clave='impresora_puerto', tienda_id=tienda_id).first()
    
    ip = conf_ip.valor if conf_ip else '192.168.0.14'
    puerto = conf_puerto.valor if conf_puerto else '9100'

    # Generar los comandos ESC/POS (Iniciar, Texto, Cortar)
    datos = impresion_service.CMD_INIT
    datos += texto.encode('cp850', errors='replace')
    datos += impresion_service.CMD_FEED * 2
    datos += impresion_service.CMD_CUT

    # Enviar a la impresora (la función detecta si es USB o Red)
    exito, mensaje = impresion_service.enviar_a_impresora(ip, puerto, datos)

    return jsonify({'ok': exito, 'mensaje': mensaje})


# ==================== RUTAS DE STOCK Y PRODUCTO ====================
@bp.route('/<int:producto_id>/stock', methods=['POST'])
@login_required
@admin_requerido
def actualizar_stock(producto_id):
    cantidad = request.form.get('cantidad', type=int)
    tienda_id = request.args.get('tienda', type=int) or tienda_actual()
    
    if cantidad is None or cantidad < 0:
        flash('Cantidad inválida', 'danger')
        return redirect(url_for('inventario.lista', tienda=tienda_id))
        
    pres = ProductoTienda.query.filter_by(producto_id=producto_id, tienda_id=tienda_id).first()
    if pres:
        pres.cantidad = cantidad
        pres.sync_estado = 'pendiente'
        db.session.commit()
        _audit('stock_actualizado', f'Producto {producto_id} actualizado a {cantidad}', tienda_id)
        flash('Stock actualizado correctamente', 'success')
    else:
        flash('Producto no encontrado en esta tienda', 'warning')
        
    return redirect(url_for('inventario.lista', tienda=tienda_id))


@bp.route('/<int:producto_id>/editar', methods=['GET', 'POST'])
@login_required
@programador_requerido
def editar(producto_id):
    prod = Producto.query.get_or_404(producto_id)
    tienda_id = request.args.get('tienda', type=int) or tienda_actual()
    pres = ProductoTienda.query.filter_by(producto_id=prod.id, tienda_id=tienda_id).first()
    
    form = ProductoForm(obj=prod)
    if form.validate_on_submit():
        prod.nombre = form.nombre.data
        prod.categoria = form.categoria.data
        prod.codigo_barras = form.codigo_barras.data
        if pres:
            pres.precio_venta = form.precio_venta.data
            pres.precio_proveedor = form.precio_proveedor.data
            pres.sync_estado = 'pendiente'
        db.session.commit()
        flash('Producto actualizado', 'success')
        return redirect(url_for('inventario.lista', tienda=tienda_id))
        
    return render_template('inventario/form.html', form=form, producto=prod, tienda_actual_obj=Tienda.query.get(tienda_id))


# ==================== CREAR PRODUCTO ====================
@bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@programador_requerido
def nuevo():
    tienda_id = request.args.get('tienda', type=int) or tienda_actual()
    form = ProductoForm()
    
    if form.validate_on_submit():
        nuevo_prod = Producto(
            nombre=form.nombre.data,
            categoria=form.categoria.data,
            codigo_barras=form.codigo_barras.data,
            codigo_global=str(uuid.uuid4())
        )
        db.session.add(nuevo_prod)
        db.session.flush()
        
        nueva_pres = ProductoTienda(
            producto_id=nuevo_prod.id,
            tienda_id=tienda_id,
            cantidad=0,
            precio_venta=form.precio_venta.data,
            precio_proveedor=form.precio_proveedor.data,
            sync_estado='pendiente'
        )
        db.session.add(nueva_pres)
        db.session.commit()
        _audit('producto_creado', f'Producto {nuevo_prod.nombre} creado', tienda_id)
        flash('Producto creado correctamente', 'success')
        return redirect(url_for('inventario.lista', tienda=tienda_id))
        
    return render_template('inventario/form.html', form=form, producto=None, tienda_actual_obj=Tienda.query.get(tienda_id))


# ==================== ELIMINAR PRODUCTO ====================
@bp.route('/<int:producto_id>/eliminar', methods=['POST'])
@login_required
@programador_requerido
def eliminar(producto_id):
    prod = Producto.query.get_or_404(producto_id)
    tienda_id = request.args.get('tienda', type=int) or tienda_actual()
    
    try:
        db.session.delete(prod)
        db.session.commit()
        _audit('producto_eliminado', f'Producto {prod.nombre} eliminado', tienda_id)
        flash('Producto eliminado del catálogo', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')
        
    return redirect(url_for('inventario.lista', tienda=tienda_id))


# ==================== STOCK MASIVO ====================
@bp.route('/stock-masivo', methods=['GET', 'POST'])
@login_required
@programador_requerido
def stock_masivo():
    tienda_id = request.args.get('tienda', type=int) or tienda_actual()
    # Esta ruta usualmente solo renderiza una plantilla para cargar un Excel o editar rápido
    return render_template('inventario/stock_masivo.html', tienda_id=tienda_id)