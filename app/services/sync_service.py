# app/services/sync_service.py
"""Logica de sincronizacion entre tienda y central."""
from datetime import datetime, timedelta
from decimal import Decimal
from flask import current_app
from app.extensions import db
from app.models.factura import Factura, DetalleFactura
from app.models.cliente import Cliente
from app.models.pago import Pago
from app.models.producto import Producto, ProductoTienda
from app.models.tienda import Tienda
from app.models.sync_log import SyncLog


def hora_local():
    return datetime.utcnow() - timedelta(hours=5)


# ==================== PUSH (TIENDA → CENTRAL) ====================
def obtener_pendientes_push(tienda_id):
    """Devuelve todos los registros pendientes de subir al central."""
    facturas_pend = (Factura.query
                     .filter_by(tienda_id=tienda_id, sync_estado='pendiente')
                     .order_by(Factura.id)
                     .limit(100)
                     .all())

    pagos_pend = (Pago.query
                  .filter_by(tienda_id=tienda_id, sync_estado='pendiente')
                  .order_by(Pago.id)
                  .limit(100)
                  .all())

    clientes_pend = (Cliente.query
                     .filter_by(tienda_id=tienda_id, sync_estado='pendiente')
                     .order_by(Cliente.id)
                     .limit(100)
                     .all())

    return {
        'facturas': [_factura_to_dict(f) for f in facturas_pend],
        'pagos': [_pago_to_dict(p) for p in pagos_pend],
        'clientes': [_cliente_to_dict(c) for c in clientes_pend],
    }


def _factura_to_dict(f):
    return {
        'id': f.id,
        'numero_factura': f.numero_factura,
        'tienda_id': f.tienda_id,
        'fecha_hora': f.fecha_hora.isoformat() if f.fecha_hora else None,
        'cliente_id': f.cliente_id,
        'usuario_id': f.usuario_id,
        'subtotal': float(f.subtotal or 0),
        'total': float(f.total or 0),
        'metodo_pago': f.metodo_pago,
        'recargo_nequi': float(f.recargo_nequi or 0),
        'recargo_bolsa': float(f.recargo_bolsa or 0),
        'valor_pagado': float(f.valor_pagado or 0),
        'vueltas': float(f.vueltas or 0),
        'tipo_pago': f.tipo_pago,
        'estado_credito': f.estado_credito,
        'saldo_pendiente': float(f.saldo_pendiente or 0),
        'detalles': [_detalle_to_dict(d) for d in f.detalles],
    }


def _detalle_to_dict(d):
    return {
        'producto_id': d.producto_id,
        'producto_nombre': d.producto_nombre,
        'cantidad': d.cantidad,
        'precio_unitario': float(d.precio_unitario or 0),
        'subtotal': float(d.subtotal or 0),
    }


def _pago_to_dict(p):
    return {
        'id': p.id,
        'factura_id': p.factura_id,
        'tienda_id': p.tienda_id,
        'fecha': p.fecha.isoformat() if p.fecha else None,
        'monto': float(p.monto or 0),
        'metodo_pago': p.metodo_pago,
    }


def _cliente_to_dict(c):
    return {
        'id': c.id,
        'tienda_id': c.tienda_id,
        'nombre': c.nombre,
        'documento': c.documento,
        'direccion': c.direccion,
        'telefono': c.telefono,
        'email': c.email,
        'saldo_actual': float(c.saldo_actual or 0),
        'creado_en': c.creado_en.isoformat() if c.creado_en else None,
    }


def marcar_sincronizados(tienda_id, resultado):
    """Marca los registros que el central confirmo como sincronizados."""
    ids_facturas = resultado.get('facturas_ok', [])
    ids_pagos = resultado.get('pagos_ok', [])
    ids_clientes = resultado.get('clientes_ok', [])

    if ids_facturas:
        (Factura.query
         .filter(Factura.id.in_(ids_facturas), Factura.tienda_id == tienda_id)
         .update({'sync_estado': 'sincronizado',
                  'sync_fecha': datetime.utcnow()},
                 synchronize_session=False))

    if ids_pagos:
        (Pago.query
         .filter(Pago.id.in_(ids_pagos), Pago.tienda_id == tienda_id)
         .update({'sync_estado': 'sincronizado',
                  'sync_fecha': datetime.utcnow()},
                 synchronize_session=False))

    if ids_clientes:
        (Cliente.query
         .filter(Cliente.id.in_(ids_clientes), Cliente.tienda_id == tienda_id)
         .update({'sync_estado': 'sincronizado',
                  'sync_fecha': datetime.utcnow()},
                 synchronize_session=False))

    db.session.commit()


# ==================== PULL (CENTRAL → TIENDA) ====================
def obtener_cambios_pull(desde):
    """Devuelve productos y configuracion modificados desde 'desde'."""
    if isinstance(desde, str):
        try:
            desde = datetime.fromisoformat(desde)
        except ValueError:
            desde = datetime.utcnow() - timedelta(days=7)

    productos = (Producto.query
                 .filter(Producto.actualizado_en >= desde)
                 .all())

    resultado = {
        'productos': [],
        'timestamp': datetime.utcnow().isoformat(),
    }

    for p in productos:
        for pres in p.presentaciones:
            resultado['productos'].append({
                'producto_id': p.id,
                'nombre': p.nombre,
                'codigo_barras': p.codigo_barras,
                'categoria': p.categoria,
                'tienda_id': pres.tienda_id,
                'precio_venta': float(pres.precio_venta or 0),
                'precio_venta1': float(pres.precio_venta1 or 0),
                'precio_venta2': float(pres.precio_venta2 or 0),
                'precio_venta3': float(pres.precio_venta3 or 0),
                'condicion1': pres.condicion1 or '',
                'condicion2': pres.condicion2 or '',
                'condicion3': pres.condicion3 or '',
            })

    return resultado


def aplicar_cambios_pull(datos):
    """Aplica los cambios recibidos del central en la tienda local."""
    actualizados = 0

    for p_data in datos.get('productos', []):
        producto_id = p_data.get('producto_id')
        tienda_id = p_data.get('tienda_id')

        pres = ProductoTienda.query.filter_by(
            producto_id=producto_id, tienda_id=tienda_id
        ).first()

        if not pres:
            continue

        pres.precio_venta = Decimal(str(p_data.get('precio_venta', 0)))
        pres.precio_venta1 = Decimal(str(p_data.get('precio_venta1', 0)))
        pres.precio_venta2 = Decimal(str(p_data.get('precio_venta2', 0)))
        pres.precio_venta3 = Decimal(str(p_data.get('precio_venta3', 0)))
        pres.condicion1 = p_data.get('condicion1', '')
        pres.condicion2 = p_data.get('condicion2', '')
        pres.condicion3 = p_data.get('condicion3', '')

        actualizados += 1

    db.session.commit()
    return actualizados


# ==================== LOG ====================
def registrar_log(tienda_id, tipo, tabla, registros, exitoso, mensaje=''):
    """Registra un log de sync. Ignora el error si tienda_id no existe (ej: modo central)."""
    try:
        # No guardar log si tienda_id es 0, negativo o None (modo central)
        if not tienda_id or tienda_id <= 0:
            return None

        # Verificar que la tienda existe
        from app.models.tienda import Tienda
        existe = db.session.query(Tienda.id).filter_by(id=tienda_id).first()
        if not existe:
            return None

        log = SyncLog(
            tienda_id=tienda_id,
            tipo=tipo,
            tabla=tabla,
            registros=registros,
            exitoso=exitoso,
            mensaje=mensaje[:500] if mensaje else '',
        )
        db.session.add(log)
        db.session.commit()
        return log
    except Exception as e:
        db.session.rollback()
        print(f'  [log] Aviso: {type(e).__name__}')
        return None