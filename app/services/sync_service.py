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


# ==================== PUSH (TIENDA -> CENTRAL) ====================
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
        'origen': getattr(f, 'origen', 'local'),
        'precio_manual': bool(getattr(f, 'precio_manual', False)),
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
    ids_productos = resultado.get('productos_ok', [])

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

    if ids_productos:
        (ProductoTienda.query
         .filter(ProductoTienda.tienda_id == tienda_id,
                 ProductoTienda.producto_id.in_(ids_productos))
         .update({'sync_estado': 'sincronizado',
                  'sync_fecha': datetime.utcnow()},
                 synchronize_session=False))

    db.session.commit()


# ==================== PULL (CENTRAL -> TIENDA) ====================
def obtener_cambios_pull(tienda_id, desde=None):
    """Devuelve los productos de UNA tienda especifica que tienen cambios
    pendientes de enviar (fue editado el precio, stock o condiciones)."""
    if not tienda_id:
        return {'productos': [], 'timestamp': datetime.utcnow().isoformat()}

    query = (db.session.query(Producto, ProductoTienda)
             .join(ProductoTienda, Producto.id == ProductoTienda.producto_id)
             .filter(
                 ProductoTienda.tienda_id == tienda_id,
                 ProductoTienda.sync_estado == 'pendiente'
             ))

    resultado = {'productos': [], 'timestamp': datetime.utcnow().isoformat()}

    for p, pres in query.all():
        resultado['productos'].append({
            'producto_id': p.id,
            'nombre': p.nombre,
            'codigo_barras': p.codigo_barras,
            'categoria': p.categoria,
            'tienda_id': pres.tienda_id,
            'cantidad': int(pres.cantidad or 0),
            'precio_venta': float(pres.precio_venta or 0),
            'precio_venta1': float(pres.precio_venta1 or 0),
            'precio_venta2': float(pres.precio_venta2 or 0),
            'precio_venta3': float(pres.precio_venta3 or 0),
            'condicion1': pres.condicion1 or '',
            'condicion2': pres.condicion2 or '',
            'condicion3': pres.condicion3 or '',
        })

    return resultado


def marcar_productos_enviados(tienda_id, ids_productos):
    """NUEVO v2.12: Marca productos de una tienda como 'sincronizado' despues
    de servirlos por /sync/pull. Evita que se repitan indefinidamente en cada
    ciclo del worker (bug v2.11: los mismos productos bajaban cada 2 min)."""
    if not ids_productos or not tienda_id:
        return 0

    n = (ProductoTienda.query
         .filter(ProductoTienda.tienda_id == tienda_id,
                 ProductoTienda.producto_id.in_(ids_productos),
                 ProductoTienda.sync_estado == 'pendiente')
         .update({
             'sync_estado': 'sincronizado',
             'sync_fecha': datetime.utcnow(),
         }, synchronize_session=False))
    db.session.commit()
    return n


def aplicar_cambios_pull(datos):
    """Aplica los cambios recibidos del central.
    IMPORTANTE: prioriza match por codigo_barras (unico y confiable)
    antes que por ID, porque los IDs pueden estar desalineados entre PCs.
    v2.12-fix-C: se elimino el fallback por ID (corrompia productos)."""
    actualizados = 0
    creados = 0

    for p_data in datos.get('productos', []):
        producto_id = p_data.get('producto_id')
        tienda_id = p_data.get('tienda_id')
        nombre = p_data.get('nombre')
        codigo = p_data.get('codigo_barras')

        if not tienda_id:
            continue

        # ============ 1. BUSCAR PRODUCTO GLOBAL (PRIORIDAD: CODIGO) ============
        producto = None

        # 1a. Por codigo de barras (lo mas confiable)
        if codigo:
            producto = Producto.query.filter_by(codigo_barras=codigo).first()

        # 1b. Por nombre exacto
        if not producto and nombre:
            producto = Producto.query.filter_by(nombre=nombre).first()

        # 1c. ELIMINADO en v2.12-fix-C: el fallback por ID corrompia productos
        # por el desfase -1 entre central y tienda. Ahora si no hay match
        # por codigo ni nombre, se crea un producto nuevo (bloque 2 abajo).

        # ============ 2. SI NO EXISTE, CREARLO ============
        if not producto:
            try:
                # v2.12-fix-C: NO forzar id=producto_id (causaba desfase
                # entre PCs). Dejar que la BD asigne el siguiente ID libre.
                producto = Producto(
                    nombre=nombre or f'Producto {producto_id}',
                    codigo_barras=codigo or None,
                    categoria=p_data.get('categoria') or None,
                )
                db.session.add(producto)
                db.session.flush()
            except Exception as e:
                db.session.rollback()
                print(f'  [pull] No se pudo crear producto {producto_id}: {e}')
                continue

        id_real = producto.id

        # ============ 3. BUSCAR/CREAR PRODUCTO_TIENDA ============
        pres = ProductoTienda.query.filter_by(
            producto_id=id_real, tienda_id=tienda_id
        ).first()

        if not pres:
            pres = ProductoTienda(
                producto_id=id_real,
                tienda_id=tienda_id,
                cantidad=0,
            )
            db.session.add(pres)
            db.session.flush()
            creados += 1

        # ============ 4. APLICAR VALORES ============
        pres.cantidad = int(p_data.get('cantidad', pres.cantidad or 0))
        pres.precio_venta = Decimal(str(p_data.get('precio_venta', 0)))
        pres.precio_venta1 = Decimal(str(p_data.get('precio_venta1', 0)))
        pres.precio_venta2 = Decimal(str(p_data.get('precio_venta2', 0)))
        pres.precio_venta3 = Decimal(str(p_data.get('precio_venta3', 0)))
        pres.condicion1 = p_data.get('condicion1', '')
        pres.condicion2 = p_data.get('condicion2', '')
        pres.condicion3 = p_data.get('condicion3', '')

        pres.sync_estado = 'sincronizado'
        pres.sync_fecha = datetime.utcnow()

        actualizados += 1

    db.session.commit()

    if creados > 0:
        print(f'  [pull] {creados} productos nuevos creados, {actualizados} actualizados')

    return actualizados


# ==================== LOG ====================
def registrar_log(tienda_id, tipo, tabla, registros, exitoso, mensaje=''):
    """Registra un log de sync. Ignora el error si tienda_id no existe (ej: modo central)."""
    try:
        if not tienda_id or tienda_id <= 0:
            return None

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


# ==================== PUSH: GUARDAR EN CENTRAL ====================
def procesar_push(tienda_id, datos):
    """Procesa los datos recibidos de una tienda y los guarda en el central."""
    from app.models.usuario import Usuario

    facturas_ok = []
    pagos_ok = []
    clientes_ok = []
    productos_ok = []
    errores = []

    # ---------- 1. CLIENTES ----------
    mapa_clientes = {}

    for c_data in datos.get('clientes', []):
        try:
            id_local = c_data.get('id')
            nombre = (c_data.get('nombre') or '').strip()
            documento = (c_data.get('documento') or '').strip()

            if not nombre:
                errores.append(f'Cliente {id_local}: sin nombre')
                continue

            query = Cliente.query.filter_by(tienda_id=tienda_id, nombre=nombre)
            if documento:
                query = query.filter_by(documento=documento)
            existente = query.first()

            if existente:
                existente.direccion = c_data.get('direccion') or existente.direccion
                existente.telefono = c_data.get('telefono') or existente.telefono
                existente.email = c_data.get('email') or existente.email
                existente.saldo_actual = Decimal(str(c_data.get('saldo_actual', 0)))
                existente.sync_estado = 'sincronizado'
                existente.sync_fecha = datetime.utcnow()
                mapa_clientes[id_local] = existente.id
            else:
                nuevo = Cliente(
                    tienda_id=tienda_id,
                    nombre=nombre,
                    documento=documento or None,
                    direccion=c_data.get('direccion') or None,
                    telefono=c_data.get('telefono') or None,
                    email=c_data.get('email') or None,
                    saldo_actual=Decimal(str(c_data.get('saldo_actual', 0))),
                    sync_estado='sincronizado',
                    sync_fecha=datetime.utcnow(),
                )
                db.session.add(nuevo)
                db.session.flush()
                mapa_clientes[id_local] = nuevo.id

            clientes_ok.append(id_local)
        except Exception as e:
            errores.append(f'Cliente {c_data.get("id")}: {e}')

    # ---------- 2. FACTURAS ----------
    mapa_facturas = {}

    for f_data in datos.get('facturas', []):
        try:
            id_local = f_data.get('id')
            numero = f_data.get('numero_factura')

            if not numero:
                errores.append(f'Factura {id_local}: sin numero_factura')
                continue

            existente = Factura.query.filter_by(
                tienda_id=tienda_id, numero_factura=numero
            ).first()

            if existente:
                mapa_facturas[id_local] = existente.id
                facturas_ok.append(id_local)
                continue

            fecha_str = f_data.get('fecha_hora')
            try:
                fecha_hora = datetime.fromisoformat(fecha_str) if fecha_str else datetime.utcnow()
            except (ValueError, TypeError):
                fecha_hora = datetime.utcnow()

            cliente_local_id = f_data.get('cliente_id')
            cliente_id_central = mapa_clientes.get(cliente_local_id, cliente_local_id)

            if cliente_id_central and not Cliente.query.get(cliente_id_central):
                cliente_gen = Cliente.query.filter_by(
                    tienda_id=tienda_id, nombre='Cliente sincronizado'
                ).first()
                if not cliente_gen:
                    cliente_gen = Cliente(
                        tienda_id=tienda_id,
                        nombre='Cliente sincronizado',
                        saldo_actual=Decimal('0'),
                    )
                    db.session.add(cliente_gen)
                    db.session.flush()
                cliente_id_central = cliente_gen.id

            usuario_id = f_data.get('usuario_id')
            if usuario_id:
                existe_user = db.session.query(Usuario.id).filter_by(id=usuario_id).first()
                if not existe_user:
                    usuario_id = None

            factura = Factura(
                numero_factura=numero,
                tienda_id=tienda_id,
                fecha_hora=fecha_hora,
                cliente_id=cliente_id_central,
                usuario_id=usuario_id,
                subtotal=Decimal(str(f_data.get('subtotal', 0))),
                total=Decimal(str(f_data.get('total', 0))),
                metodo_pago=f_data.get('metodo_pago', ''),
                recargo_nequi=Decimal(str(f_data.get('recargo_nequi', 0))),
                recargo_bolsa=Decimal(str(f_data.get('recargo_bolsa', 0))),
                valor_pagado=Decimal(str(f_data.get('valor_pagado', 0))),
                vueltas=Decimal(str(f_data.get('vueltas', 0))),
                tipo_pago=f_data.get('tipo_pago', 'contado'),
                estado_credito=f_data.get('estado_credito', 'pagado'),
                saldo_pendiente=Decimal(str(f_data.get('saldo_pendiente', 0))),
                origen='local',
                precio_manual=bool(f_data.get('precio_manual', False)),
                sync_estado='sincronizado',
                sync_fecha=datetime.utcnow(),
            )
            db.session.add(factura)
            db.session.flush()

            for d in f_data.get('detalles', []):
                detalle = DetalleFactura(
                    factura_id=factura.id,
                    producto_id=d.get('producto_id') or 1,
                    producto_nombre=d.get('producto_nombre', ''),
                    cantidad=int(d.get('cantidad', 0)),
                    precio_unitario=Decimal(str(d.get('precio_unitario', 0))),
                    subtotal=Decimal(str(d.get('subtotal', 0))),
                )
                db.session.add(detalle)

            mapa_facturas[id_local] = factura.id
            facturas_ok.append(id_local)
        except Exception as e:
            errores.append(f'Factura {f_data.get("id")}: {e}')

    # ---------- 3. PAGOS ----------
    for p_data in datos.get('pagos', []):
        try:
            id_local = p_data.get('id')
            factura_local_id = p_data.get('factura_id')
            factura_central_id = mapa_facturas.get(factura_local_id)

            if not factura_central_id:
                errores.append(f'Pago {id_local}: factura {factura_local_id} no mapeada')
                continue

            monto = Decimal(str(p_data.get('monto', 0)))

            existente = Pago.query.filter_by(
                factura_id=factura_central_id, monto=monto
            ).first()
            if existente:
                pagos_ok.append(id_local)
                continue

            fecha_str = p_data.get('fecha')
            try:
                fecha_pago = datetime.fromisoformat(fecha_str) if fecha_str else datetime.utcnow()
            except (ValueError, TypeError):
                fecha_pago = datetime.utcnow()

            pago = Pago(
                factura_id=factura_central_id,
                tienda_id=tienda_id,
                fecha=fecha_pago,
                monto=monto,
                metodo_pago=p_data.get('metodo_pago', 'efectivo'),
                sync_estado='sincronizado',
                sync_fecha=datetime.utcnow(),
            )
            db.session.add(pago)
            db.session.flush()
            pagos_ok.append(id_local)
        except Exception as e:
            errores.append(f'Pago {p_data.get("id")}: {e}')

    # ---------- 4. PRODUCTOS (precios/stock editados en tienda) ----------
    for p_data in datos.get('productos', []):
        try:
            producto_id = p_data.get('producto_id')
            t_id = p_data.get('tienda_id')
            codigo = p_data.get('codigo_barras')
            nombre = p_data.get('nombre')

            if not t_id:
                continue

            # v2.12-fix-B: buscar producto SOLO por codigo o nombre.
            # NUNCA por ID: los IDs estan desalineados entre PCs y el
            # fallback corrompia productos. Si no hay match, se registra error.
            producto = None
            if codigo:
                producto = Producto.query.filter_by(codigo_barras=codigo).first()
            if not producto and nombre:
                producto = Producto.query.filter_by(nombre=nombre).first()

            if not producto:
                errores.append(f'Producto {producto_id}: no existe en central')
                continue

            pres = ProductoTienda.query.filter_by(
                producto_id=producto.id, tienda_id=t_id
            ).first()

            if not pres:
                errores.append(f'Producto {producto_id}: no existe presentacion en central')
                continue

            pres.cantidad = int(p_data.get('cantidad', pres.cantidad or 0))
            pres.precio_venta = Decimal(str(p_data.get('precio_venta', 0)))
            pres.precio_venta1 = Decimal(str(p_data.get('precio_venta1', 0)))
            pres.precio_venta2 = Decimal(str(p_data.get('precio_venta2', 0)))
            pres.precio_venta3 = Decimal(str(p_data.get('precio_venta3', 0)))
            pres.condicion1 = p_data.get('condicion1', '')
            pres.condicion2 = p_data.get('condicion2', '')
            pres.condicion3 = p_data.get('condicion3', '')

            pres.sync_estado = 'sincronizado'
            pres.sync_fecha = datetime.utcnow()

            # Devolver el ID REAL del producto (no el que vino)
            productos_ok.append(producto_id)
        except Exception as e:
            errores.append(f'Producto {p_data.get("producto_id")}: {e}')

    db.session.commit()

    return {
        'facturas_ok': facturas_ok,
        'pagos_ok': pagos_ok,
        'clientes_ok': clientes_ok,
        'productos_ok': productos_ok,
        'errores': errores,
    }


# ==================== PULL FACTURAS (CENTRAL -> TIENDA) ====================
def obtener_facturas_para_tienda(tienda_id, desde=None):
    """Devuelve SOLO las facturas remotas pendientes para esa tienda."""
    query = Factura.query.filter(
        Factura.tienda_id == tienda_id,
        Factura.origen == 'remota',
    )

    if desde:
        try:
            if isinstance(desde, str):
                desde = datetime.fromisoformat(desde)
            query = query.filter(Factura.fecha_hora >= desde)
        except (ValueError, TypeError):
            pass

    facturas = query.order_by(Factura.fecha_hora.asc()).limit(100).all()

    resultado = []
    for f in facturas:
        cliente_data = None
        if f.cliente:
            cliente_data = {
                'nombre': f.cliente.nombre,
                'documento': f.cliente.documento or '',
                'direccion': f.cliente.direccion or '',
                'telefono': f.cliente.telefono or '',
                'email': f.cliente.email or '',
                'saldo_actual': float(f.cliente.saldo_actual or 0),
            }

        detalles = []
        for d in f.detalles.all():
            detalles.append({
                'producto_id': d.producto_id,
                'producto_nombre': d.producto_nombre,
                'cantidad': d.cantidad,
                'precio_unitario': float(d.precio_unitario or 0),
                'subtotal': float(d.subtotal or 0),
            })

        resultado.append({
            'id': f.id,
            'numero_factura': f.numero_factura,
            'tienda_id': f.tienda_id,
            'fecha_hora': f.fecha_hora.isoformat() if f.fecha_hora else None,
            'cliente': cliente_data,
            'usuario_nombre': f.usuario.nombre if f.usuario else None,
            'subtotal': float(f.subtotal or 0),
            'total': float(f.total or 0),
            'metodo_pago': f.metodo_pago or '',
            'recargo_nequi': float(f.recargo_nequi or 0),
            'recargo_bolsa': float(f.recargo_bolsa or 0),
            'valor_pagado': float(f.valor_pagado or 0),
            'vueltas': float(f.vueltas or 0),
            'tipo_pago': f.tipo_pago or 'contado',
            'estado_credito': f.estado_credito or 'pagado',
            'saldo_pendiente': float(f.saldo_pendiente or 0),
            'precio_manual': bool(getattr(f, 'precio_manual', False)),
            'detalles': detalles,
        })

    return resultado


def marcar_facturas_enviadas(ids):
    """Marca facturas remotas como ya enviadas (evita reenvios)."""
    if not ids:
        return 0

    n = (Factura.query
         .filter(Factura.id.in_(ids))
         .update({
             'origen': 'remota_recibida',
             'sync_fecha': datetime.utcnow(),
         }, synchronize_session=False))
    db.session.commit()
    return n


def aplicar_facturas_recibidas(tienda_id, facturas):
    """Aplica las facturas recibidas del central en la BD local."""
    insertadas = 0
    omitidas = 0

    for f_data in facturas:
        numero = f_data.get('numero_factura')
        if not numero:
            continue

        existente = Factura.query.filter_by(
            tienda_id=tienda_id, numero_factura=numero
        ).first()
        if existente:
            omitidas += 1
            continue

        cliente_local_id = None
        c_data = f_data.get('cliente')
        if c_data and c_data.get('nombre'):
            nombre = c_data['nombre'].strip()
            documento = (c_data.get('documento') or '').strip()

            query = Cliente.query.filter_by(tienda_id=tienda_id, nombre=nombre)
            if documento:
                query = query.filter_by(documento=documento)
            cliente_local = query.first()

            if not cliente_local:
                cliente_local = Cliente(
                    tienda_id=tienda_id,
                    nombre=nombre,
                    documento=documento or None,
                    direccion=c_data.get('direccion') or None,
                    telefono=c_data.get('telefono') or None,
                    email=c_data.get('email') or None,
                    saldo_actual=Decimal(str(c_data.get('saldo_actual', 0))),
                    sync_estado='sincronizado',
                    sync_fecha=datetime.utcnow(),
                )
                db.session.add(cliente_local)
                db.session.flush()

            cliente_local_id = cliente_local.id

        if not cliente_local_id:
            cliente_gen = Cliente.query.filter_by(
                tienda_id=tienda_id, nombre='Cliente remoto'
            ).first()
            if not cliente_gen:
                cliente_gen = Cliente(
                    tienda_id=tienda_id,
                    nombre='Cliente remoto',
                    saldo_actual=Decimal('0'),
                )
                db.session.add(cliente_gen)
                db.session.flush()
            cliente_local_id = cliente_gen.id

        fecha_hora = datetime.utcnow()
        if f_data.get('fecha_hora'):
            try:
                fecha_hora = datetime.fromisoformat(f_data['fecha_hora'])
            except (ValueError, TypeError):
                pass

        factura = Factura(
            numero_factura=numero,
            tienda_id=tienda_id,
            fecha_hora=fecha_hora,
            cliente_id=cliente_local_id,
            usuario_id=None,
            subtotal=Decimal(str(f_data.get('subtotal', 0))),
            total=Decimal(str(f_data.get('total', 0))),
            metodo_pago=f_data.get('metodo_pago', ''),
            recargo_nequi=Decimal(str(f_data.get('recargo_nequi', 0))),
            recargo_bolsa=Decimal(str(f_data.get('recargo_bolsa', 0))),
            valor_pagado=Decimal(str(f_data.get('valor_pagado', 0))),
            vueltas=Decimal(str(f_data.get('vueltas', 0))),
            tipo_pago=f_data.get('tipo_pago', 'contado'),
            estado_credito=f_data.get('estado_credito', 'pagado'),
            saldo_pendiente=Decimal(str(f_data.get('saldo_pendiente', 0))),
            origen='remota_recibida',
            precio_manual=bool(f_data.get('precio_manual', False)),
            sync_estado='sincronizado',
            sync_fecha=datetime.utcnow(),
        )
        db.session.add(factura)
        db.session.flush()

        for d in f_data.get('detalles', []):
            detalle = DetalleFactura(
                factura_id=factura.id,
                producto_id=d.get('producto_id') or 1,
                producto_nombre=d.get('producto_nombre', ''),
                cantidad=int(d.get('cantidad', 0)),
                precio_unitario=Decimal(str(d.get('precio_unitario', 0))),
                subtotal=Decimal(str(d.get('subtotal', 0))),
            )
            db.session.add(detalle)

        insertadas += 1

    db.session.commit()
    return insertadas


# ==================== HELPERS DE FORMATO ====================
def _factura_to_dict_extendida(f):
    """Convierte una factura a dict CON cliente y detalles (formato pull-facturas)."""
    cliente_data = None
    if f.cliente:
        cliente_data = {
            'nombre': f.cliente.nombre,
            'documento': f.cliente.documento or '',
            'direccion': f.cliente.direccion or '',
            'telefono': f.cliente.telefono or '',
            'email': f.cliente.email or '',
            'saldo_actual': float(f.cliente.saldo_actual or 0),
        }
    detalles = []
    for d in f.detalles.all():
        detalles.append({
            'producto_id': d.producto_id,
            'producto_nombre': d.producto_nombre,
            'cantidad': d.cantidad,
            'precio_unitario': float(d.precio_unitario or 0),
            'subtotal': float(d.subtotal or 0),
        })
    return {
        'id': f.id,
        'numero_factura': f.numero_factura,
        'tienda_id': f.tienda_id,
        'fecha_hora': f.fecha_hora.isoformat() if f.fecha_hora else None,
        'cliente': cliente_data,
        'usuario_nombre': f.usuario.nombre if f.usuario else None,
        'subtotal': float(f.subtotal or 0),
        'total': float(f.total or 0),
        'metodo_pago': f.metodo_pago or '',
        'recargo_nequi': float(f.recargo_nequi or 0),
        'recargo_bolsa': float(f.recargo_bolsa or 0),
        'valor_pagado': float(f.valor_pagado or 0),
        'vueltas': float(f.vueltas or 0),
        'tipo_pago': f.tipo_pago or 'contado',
        'estado_credito': f.estado_credito or 'pagado',
        'saldo_pendiente': float(f.saldo_pendiente or 0),
        'origen': getattr(f, 'origen', 'local'),
        'precio_manual': bool(getattr(f, 'precio_manual', False)),
        'detalles': detalles,
    }


# ==================== PUSH INMEDIATO (TIENDA -> CENTRAL) ====================
def push_factura_individual(tienda_id, factura_id):
    """Empuja UNA factura (y su cliente) al central inmediatamente."""
    import requests
    from flask import current_app

    factura = db.session.get(Factura, factura_id)
    if not factura:
        return False

    central_url = (current_app.config.get('CENTRAL_URL') or '').rstrip('/')
    sync_key = current_app.config.get('SYNC_KEY') or ''
    if not central_url or not sync_key:
        return False

    payload = {
        'tienda_id': tienda_id,
        'facturas': [_factura_to_dict(factura)],
        'pagos': [],
        'clientes': [_cliente_to_dict(factura.cliente)] if factura.cliente else [],
    }

    try:
        r = requests.post(
            central_url + '/api/sync/push',
            json=payload,
            headers={'X-Sync-Key': sync_key},
            timeout=8,
        )
        if r.status_code != 200:
            return False
        data = r.json()
        if not data.get('ok'):
            return False
        marcar_sincronizados(tienda_id, data)
        return True
    except requests.RequestException:
        return False


# ==================== DETECTAR FACTURAS FANTASMA ====================
def detectar_facturas_faltantes(tienda_id):
    """
    Consulta al central que facturas marcadas como 'sincronizado' en tienda
    NO existen alla (fantasmas). Las re-marca como 'pendiente'.
    Retorna cantidad de facturas re-marcadas.
    """
    import requests
    from flask import current_app

    central_url = (current_app.config.get('CENTRAL_URL') or '').rstrip('/')
    sync_key = current_app.config.get('SYNC_KEY') or ''
    if not central_url or not sync_key:
        return 0

    facturas = Factura.query.filter(
        Factura.tienda_id == tienda_id,
        Factura.sync_estado == 'sincronizado',
        Factura.origen != 'remota_recibida',
    ).all()

    if not facturas:
        return 0

    numeros = [f.numero_factura for f in facturas]

    try:
        r = requests.post(
            central_url + '/api/sync/facturas-existen',
            json={'tienda_id': tienda_id, 'numeros': numeros},
            headers={'X-Sync-Key': sync_key},
            timeout=15,
        )
        if r.status_code != 200:
            return 0
        data = r.json()
        if not data.get('ok'):
            return 0

        faltan = data.get('faltan', [])
        if not faltan:
            return 0

        n = (Factura.query
             .filter(Factura.tienda_id == tienda_id,
                     Factura.numero_factura.in_(faltan))
             .update({'sync_estado': 'pendiente'}, synchronize_session=False))
        db.session.commit()
        return n

    except requests.RequestException:
        return 0


# ==================== PRODUCTOS PENDIENTES DE PUSH ====================
def obtener_productos_pendientes_push(tienda_id):
    """Devuelve los productos LOCALES de esta tienda que fueron editados
    (precio o stock) y hay que enviar al central."""
    query = ProductoTienda.query.filter_by(
        tienda_id=tienda_id,
        sync_estado='pendiente'
    ).all()

    resultado = []
    for pres in query:
        # Incluir nombre y codigo para que central pueda hacer el match correcto
        prod = pres.producto
        resultado.append({
            'producto_id': pres.producto_id,
            'tienda_id': pres.tienda_id,
            'nombre': prod.nombre if prod else None,
            'codigo_barras': prod.codigo_barras if prod else None,
            'cantidad': int(pres.cantidad or 0),
            'precio_venta': float(pres.precio_venta or 0),
            'precio_venta1': float(pres.precio_venta1 or 0),
            'precio_venta2': float(pres.precio_venta2 or 0),
            'precio_venta3': float(pres.precio_venta3 or 0),
            'condicion1': pres.condicion1 or '',
            'condicion2': pres.condicion2 or '',
            'condicion3': pres.condicion3 or '',
        })

    return resultado