# app/blueprints/facturacion/routes.py
from decimal import Decimal
from flask import (
    render_template, request, jsonify, redirect, url_for,
    flash, current_app, session, send_from_directory
)
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from . import bp
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.tienda import Tienda
from app.models.cliente import Cliente
from app.models.factura import Factura, DetalleFactura
from app.blueprints.configuracion.routes import get_valor
from app.services.facturacion_service import (
    crear_factura_completa, obtener_o_crear_cliente
)
import os

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


@bp.route('/')
@login_required
def nueva():
    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()
    tienda_actual_obj = Tienda.query.get(tienda_id) if tienda_id else None

    try:
        recargo = float(get_valor('recargo_nequi', None) or 0.4)
    except (ValueError, TypeError):
        recargo = 0.4

    try:
        valor_bolsa_config = int(get_valor('valor_bolsa', None) or 100)
    except (ValueError, TypeError):
        valor_bolsa_config = 100

    return render_template(
        'facturacion/nueva.html',
        tienda_id=tienda_id,
        tienda_actual_obj=tienda_actual_obj,
        tiendas=tiendas,
        recargo_porcentaje=recargo,
        valor_bolsa=valor_bolsa_config,
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

    patron_unaccent = func.unaccent(f'%{q}%')
    q_lower = q.lower()
    empieza_con_numero = q[0].isdigit() if q else False

    # FILTRO DE INACTIVOS APLICADO EN TODAS LAS BUSQUEDAS
    if empieza_con_numero:
        productos = (Producto.query
                     .filter(func.coalesce(Producto.categoria, '') != 'INACTIVO')
                     .filter(Producto.codigo_barras.ilike(f'%{q}%'))
                     .order_by(Producto.nombre).limit(20).all())
        if not productos:
            productos = (Producto.query
                         .filter(func.coalesce(Producto.categoria, '') != 'INACTIVO')
                         .filter(func.unaccent(Producto.nombre).ilike(patron_unaccent))
                         .order_by(Producto.nombre).limit(20).all())
    else:
        productos = (Producto.query
                     .filter(func.coalesce(Producto.categoria, '') != 'INACTIVO')
                     .filter(func.unaccent(Producto.nombre).ilike(patron_unaccent))
                     .limit(50).all())

        if productos:
            def prioridad(prod):
                nombre_lower = (prod.nombre or '').lower()
                if nombre_lower.startswith(q_lower): return (1, nombre_lower)
                for palabra in nombre_lower.split():
                    if palabra.startswith(q_lower): return (2, nombre_lower)
                return (3, nombre_lower)
            productos = sorted(productos, key=prioridad)[:20]
        else:
            productos = (Producto.query
                         .filter(func.coalesce(Producto.categoria, '') != 'INACTIVO')
                         .filter(Producto.codigo_barras.ilike(f'%{q}%'))
                         .order_by(Producto.nombre).limit(20).all())

    resultados = []
    for p in productos:
        pres = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=tienda_id).first()
        if not pres:
            continue
        resultados.append({
            'id': p.id, 
            'nombre': p.nombre, 
            'codigo': p.codigo_barras or '',
            'categoria': p.categoria or '', 
            'imagen': p.imagen or '',
            'stock': pres.cantidad,
            'precio': float(pres.precio_venta or 0),
            'condicion1': pres.condicion1 or '', 'precio1': float(pres.precio_venta1 or 0),
            'condicion2': pres.condicion2 or '', 'precio2': float(pres.precio_venta2 or 0),
            'condicion3': pres.condicion3 or '', 'precio3': float(pres.precio_venta3 or 0),
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
                .limit(10).all())

    return jsonify([{
        'id': c.id, 'nombre': c.nombre, 'documento': c.documento or '',
        'telefono': c.telefono or '', 'direccion': c.direccion or '',
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
            valor_bolsa=Decimal(str(int(get_valor('valor_bolsa', None) or 100))),
            valor_pagado=Decimal(str(data.get('valor_pagado', 0))),
            pagos=data.get('pagos'),
            precio_manual=bool(data.get('precio_manual', False)),
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
            'id': c.id, 'nombre': c.nombre, 'documento': c.documento or '',
            'telefono': c.telefono or '', 'direccion': c.direccion or '',
            'saldo': float(c.saldo_actual or 0),
        })
    return jsonify(None)

# ==================== FOTO EN HD ====================
@bp.route('/imagen-hd/<int:producto_id>')
@login_required
def imagen_hd(producto_id):
    prod = Producto.query.get(producto_id)
    if not prod:
        return "Producto no encontrado", 404

    codigo = prod.codigo_barras or f"PROD-{prod.id}"
    
    # Ruta absoluta basada en el root_path de la app (100% segura)
    BASE_DIR = os.path.dirname(current_app.root_path)

    # 1. Buscar el original en data/imagenes (agregamos .webp y mayúsculas)
    img_dir = os.path.join(BASE_DIR, 'data', 'imagenes')
    for ext in ['.jpeg', '.jpg', '.png', '.JPG', '.JPEG', '.PNG', '.webp', '.WEBP']:
        filename = f"{codigo}{ext}"
        if os.path.exists(os.path.join(img_dir, filename)):
            return send_from_directory(img_dir, filename)

    # 2. Si ya se procesó, buscar en data/imagenes_procesadas
    img_dir_proc = os.path.join(BASE_DIR, 'data', 'imagenes_procesadas')
    for ext in ['.jpeg', '.jpg', '.png', '.JPG', '.JPEG', '.PNG', '.webp', '.WEBP']:
        filename = f"{codigo}{ext}"
        if os.path.exists(os.path.join(img_dir_proc, filename)):
            return send_from_directory(img_dir_proc, filename)

    # 3. Si no hay original, devolver la miniatura webp
    static_dir = os.path.join(BASE_DIR, 'app', 'static', 'img', 'productos')
    filename = f"{codigo}.webp"
    if os.path.exists(os.path.join(static_dir, filename)):
        return send_from_directory(static_dir, filename)

    return "Imagen no encontrada", 404