# app/blueprints/venta_rapida/routes.py
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
