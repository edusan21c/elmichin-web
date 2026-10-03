# app/services/facturacion_service.py
"""Logica de negocio para facturacion."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.cliente import Cliente
from app.models.factura import Factura, DetalleFactura
from app.models.venta import Venta


def hora_local():
    return datetime.utcnow() - timedelta(hours=5)


def redondear(v):
    return Decimal(str(v or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def generar_numero_factura(tienda_id, origen='local'):
    """Genera numero unico. Central usa REM-, tienda usa FAC-."""
    prefijo = 'REM' if origen == 'remota' else 'FAC'
    patron = f'{prefijo}-T{tienda_id}-%'

    ultima = (Factura.query
              .filter(Factura.tienda_id == tienda_id)
              .filter(Factura.numero_factura.like(patron))
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

    return f'{prefijo}-T{tienda_id}-{siguiente:04d}'


def obtener_o_crear_cliente(tienda_id, nombre, documento='', direccion='', telefono='', email=''):
    """Busca cliente por nombre+documento o lo crea."""
    nombre = (nombre or '').strip()
    documento = (documento or '').strip()

    query = Cliente.query.filter_by(tienda_id=tienda_id, nombre=nombre)
    if documento:
        query = query.filter_by(documento=documento)
    cliente = query.first()

    if cliente:
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
    origen=None,                     # None = autodetectar por MODO
):
    """Crea factura completa con validaciones y actualizaciones."""
    if not carrito:
        return None, 'El carrito esta vacio'

    # Autodetectar origen según MODO si no viene explícito
    if origen is None:
        from flask import current_app
        modo = (current_app.config.get('MODO', '') or '').lower()
        origen = 'remota' if modo == 'central' else 'local'

    items_procesados = []
    subtotal = Decimal('0')

    for item in carrito:
        producto_id = int(item['producto_id'])
        cantidad = int(item['cantidad'])
        if cantidad <= 0:
            return None, f'Cantidad invalida'

        producto = Producto.query.get(producto_id)
        if not producto:
            return None, f'Producto no encontrado'

        pres = ProductoTienda.query.filter_by(
            producto_id=producto_id, tienda_id=tienda_id
        ).first()
        if not pres:
            return None, f'Producto "{producto.nombre}" no disponible'

        if pres.cantidad < cantidad:
            return None, f'Stock insuficiente para "{producto.nombre}" (disponible: {pres.cantidad})'

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

    recargo = Decimal('0')
    if metodo_pago in ('nequi', 'daviplata'):
        recargo = redondear(subtotal * (Decimal(str(recargo_porcentaje)) / Decimal('100')))

    total_bolsas = redondear(Decimal(str(bolsas_cantidad)) * Decimal(str(valor_bolsa)))
    total_final = redondear(subtotal + recargo + total_bolsas)

    if metodo_pago == 'credito':
        valor_pagado = Decimal('0')
        vueltas = Decimal('0')
        saldo_pendiente = total_final
    else:
        valor_pagado = redondear(valor_pagado)
        if valor_pagado < total_final - Decimal('0.01'):
            return None, f'Faltan ${total_final - valor_pagado:.0f}'
        vueltas = redondear(valor_pagado - total_final)
        saldo_pendiente = Decimal('0')

    cliente = obtener_o_crear_cliente(
        tienda_id,
        cliente_data.get('nombre', 'Cliente ocasional'),
        cliente_data.get('documento', ''),
        cliente_data.get('direccion', ''),
        cliente_data.get('telefono', ''),
        cliente_data.get('email', ''),
    )

    # Si es remota, el cliente nace en central (no re-subir por push)
    if origen == 'remota':
        cliente.sync_estado = 'sincronizado'
        cliente.sync_fecha = datetime.utcnow()

    numero = generar_numero_factura(tienda_id, origen=origen)
    
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
        origen=origen,
    )
    db.session.add(factura)
    db.session.flush()

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

    if saldo_pendiente > 0:
        cliente.saldo_actual = redondear(Decimal(str(cliente.saldo_actual or 0)) + saldo_pendiente)

    db.session.commit()
    return factura.id, None
