# app/services/sync_service.py
"""Logica de sincronizacion entre tienda y central."""
import uuid
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
        'cliente_nombre': f.cliente.nombre if f.cliente else None,
        'cliente_documento': f.cliente.documento if f.cliente else None,
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
        'codigo_barras': d.producto.codigo_barras if d.producto else '',
        'producto_nombre': d.producto_nombre,
        'cantidad': d.cantidad,
        'precio_unitario': float(d.precio_unitario or 0),
        'subtotal': float(d.subtotal or 0),
    }


def _pago_to_dict(p):
    num_fact = None
    if p.factura_id:
        try:
            fact = db.session.get(Factura, p.factura_id)
            if fact:
                num_fact = fact.numero_factura
        except Exception:
            pass
    return {
        'id': p.id,
        'factura_id': p.factura_id,
        'numero_factura': num_fact,
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

    if resultado.get('configuracion_ok'):
        from app.models.configuracion import Configuracion
        (Configuracion.query
         .filter(Configuracion.tienda_id.is_(None),
                 Configuracion.sync_estado == 'pendiente')
         .update({'sync_estado': 'sincronizado',
                  'sync_fecha': datetime.utcnow()},
                 synchronize_session=False))

    db.session.commit()


# ==================== PULL (CENTRAL -> TIENDA) ====================
def obtener_cambios_pull(tienda_id, desde=None, limite=200):
    if not tienda_id:
        return {'productos': [], 'timestamp': datetime.utcnow().isoformat(),
                'hay_mas': False}

    query = (db.session.query(Producto, ProductoTienda)
             .join(ProductoTienda, Producto.id == ProductoTienda.producto_id)
             .filter(
                 ProductoTienda.tienda_id == tienda_id,
                 ProductoTienda.sync_estado == 'pendiente'
             )
             .order_by(ProductoTienda.producto_id)
             .limit(limite + 1))

    registros = query.all()
    hay_mas = len(registros) > limite
    registros = registros[:limite]

    resultado = {
        'productos': [],
        'timestamp': datetime.utcnow().isoformat(),
        'hay_mas': hay_mas,
    }

    for p, pres in registros:
        resultado['productos'].append({
            'producto_id': p.id,
            'nombre': p.nombre,
            'codigo_barras': p.codigo_barras,
            'codigo_global': p.codigo_global,
            'categoria': p.categoria,
            'tienda_id': pres.tienda_id,
            'cantidad': int(pres.cantidad or 0),
            'precio_proveedor': float(pres.precio_proveedor or 0),
            'precio_proveedor2': float(pres.precio_proveedor2 or 0),
            'precio_proveedor3': float(pres.precio_proveedor3 or 0),
            'porcentaje': float(pres.porcentaje or 0),
            'precio_venta': float(pres.precio_venta or 0),
            'precio_venta1': float(pres.precio_venta1 or 0),
            'precio_venta2': float(pres.precio_venta2 or 0),
            'precio_venta3': float(pres.precio_venta3 or 0),
            'condicion1': pres.condicion1 or '',
            'condicion2': pres.condicion2 or '',
            'condicion3': pres.condicion3 or '',
        })

    return resultado


def marcar_productos_ack(tienda_id, ids_productos):
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


def marcar_productos_enviados(tienda_id, ids_productos):
    return marcar_productos_ack(tienda_id, ids_productos)


def aplicar_cambios_pull(datos):
    """Aplica cambios recibidos del central. TODOS los campos bidireccionales."""
    actualizados = 0
    creados = 0
    ids_aplicados = []

    for p_data in datos.get('productos', []):
        producto_id = p_data.get('producto_id')
        tienda_id = p_data.get('tienda_id')
        nombre = p_data.get('nombre')
        codigo = p_data.get('codigo_barras')

        if not tienda_id:
            continue

        codigo_global = p_data.get('codigo_global')

        # v2.54: matchear primero por codigo_global, después barcode, después nombre
        producto = None
        if codigo_global:
            producto = Producto.query.filter_by(codigo_global=codigo_global).first()
        if not producto and codigo:
            producto = Producto.query.filter_by(codigo_barras=codigo).first()
        if not producto and nombre:
            producto = Producto.query.filter_by(nombre=nombre).first()

        if not producto:
            try:
                producto = Producto(
                    nombre=nombre or f'Producto {producto_id}',
                    codigo_barras=codigo or None,
                    categoria=p_data.get('categoria') or None,
                    codigo_global=codigo_global or str(uuid.uuid4()),
                )
                db.session.add(producto)
                db.session.flush()
            except Exception as e:
                db.session.rollback()
                print(f'  [pull] No se pudo crear producto {producto_id}: {e}')
                continue
        elif codigo_global and producto.codigo_global != codigo_global:
            # v2.54-fix-alinear-uuid: Central es la fuente de verdad para UUIDs.
            # Si T1 tenía un UUID distinto para el mismo producto, adoptar el de Central.
            uuid_viejo = producto.codigo_global[:8] if producto.codigo_global else "None"
            print(f'  [pull] UUID alineado: "{producto.nombre}" '
                  f'({uuid_viejo}... -> {codigo_global[:8]}...)')
            producto.codigo_global = codigo_global

        # Barcode
        if producto and codigo and producto.codigo_barras != codigo:
            codigo_anterior = producto.codigo_barras
            otro = Producto.query.filter(
                Producto.codigo_barras == codigo,
                Producto.id != producto.id,
            ).first()
            if otro:
                print(f'  [pull] Barcode {codigo} ya existe en "{otro.nombre}"')
            else:
                producto.codigo_barras = codigo
                print(f'  [pull] Barcode actualizado: "{producto.nombre}" '
                      f'{codigo_anterior} -> {codigo}')

        # Categoria
        if producto and p_data.get('categoria') is not None:
            cat_nueva = (p_data.get('categoria') or '').strip()
            if cat_nueva and producto.categoria != cat_nueva:
                print(f'  [pull] Categoria actualizada: "{producto.nombre}" '
                      f'-> {cat_nueva}')
                producto.categoria = cat_nueva

        # Nombre
        if producto and nombre and producto.nombre != nombre:
            nombre_anterior = producto.nombre
            print(f'  [pull] Nombre actualizado: "{nombre_anterior}" -> "{nombre}"')
            producto.nombre = nombre

        id_real = producto.id

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

        # Todos los campos de ProductoTienda
        pres.cantidad = int(p_data.get('cantidad', pres.cantidad or 0))
        pres.precio_proveedor = Decimal(str(p_data.get('precio_proveedor', pres.precio_proveedor or 0)))
        pres.precio_proveedor2 = Decimal(str(p_data.get('precio_proveedor2', pres.precio_proveedor2 or 0)))
        pres.precio_proveedor3 = Decimal(str(p_data.get('precio_proveedor3', pres.precio_proveedor3 or 0)))
        pres.porcentaje = Decimal(str(p_data.get('porcentaje', pres.porcentaje or 0)))
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
        ids_aplicados.append(producto_id)

    db.session.commit()

    if creados > 0:
        print(f'  [pull] {creados} productos nuevos creados, {actualizados} actualizados')

    return {
        'actualizados': actualizados,
        'creados': creados,
        'ids_aplicados': ids_aplicados,
    }


# ==================== LOG ====================
def registrar_log(tienda_id, tipo, tabla, registros, exitoso, mensaje=''):
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
    """Procesa datos del push. TODOS los campos son bidireccionales."""
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
                existente.saldo_pendiente = Decimal(str(f_data.get('saldo_pendiente', existente.saldo_pendiente or 0)))
                existente.valor_pagado = Decimal(str(f_data.get('valor_pagado', existente.valor_pagado or 0)))
                existente.estado_credito = f_data.get('estado_credito', existente.estado_credito)
                existente.tipo_pago = f_data.get('tipo_pago', existente.tipo_pago)
                existente.metodo_pago = f_data.get('metodo_pago', existente.metodo_pago)
                existente.sync_estado = 'sincronizado'
                existente.sync_fecha = datetime.utcnow()
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
                nombre_cli = (f_data.get('cliente_nombre') or '').strip()
                doc_cli = (f_data.get('cliente_documento') or '').strip()
                cliente_encontrado = None
                if nombre_cli:
                    q = Cliente.query.filter_by(tienda_id=tienda_id, nombre=nombre_cli)
                    if doc_cli:
                        q = q.filter_by(documento=doc_cli)
                    cliente_encontrado = q.first()
                if cliente_encontrado:
                    cliente_id_central = cliente_encontrado.id
                elif nombre_cli:
                    nuevo_cli = Cliente(
                        tienda_id=tienda_id, nombre=nombre_cli, documento=doc_cli or None,
                        saldo_actual=Decimal('0'), sync_estado='sincronizado',
                        sync_fecha=datetime.utcnow(),
                    )
                    db.session.add(nuevo_cli)
                    db.session.flush()
                    cliente_id_central = nuevo_cli.id

            if not cliente_id_central or not Cliente.query.get(cliente_id_central):
                cliente_gen = Cliente.query.filter_by(
                    tienda_id=tienda_id, nombre='Cliente sincronizado'
                ).first()
                if not cliente_gen:
                    cliente_gen = Cliente(
                        tienda_id=tienda_id, nombre='Cliente sincronizado',
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
                numero_factura=numero, tienda_id=tienda_id, fecha_hora=fecha_hora,
                cliente_id=cliente_id_central, usuario_id=usuario_id,
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
                sync_estado='sincronizado', sync_fecha=datetime.utcnow(),
            )
            db.session.add(factura)
            db.session.flush()

            for d in f_data.get('detalles', []):
                prod_local_id = d.get('producto_id')
                prod_nombre = (d.get('producto_nombre') or '').strip()
                prod_real = None
                if prod_nombre:
                    prod_real = Producto.query.filter_by(nombre=prod_nombre).first()
                if not prod_real:
                    codigo_tmp = f'AUTO-{prod_local_id}' if prod_local_id else None
                    if codigo_tmp:
                        prod_real = Producto.query.filter_by(codigo_barras=codigo_tmp).first()
                    if not prod_real:
                        try:
                            prod_real = Producto(
                                nombre=prod_nombre or f'Producto {prod_local_id}',
                                codigo_barras=codigo_tmp, categoria=None,
                            )
                            db.session.add(prod_real)
                            db.session.flush()
                        except Exception as e:
                            db.session.rollback()
                            errores.append(f'Detalle: no se pudo crear producto ({e})')
                            continue

                detalle = DetalleFactura(
                    factura_id=factura.id, producto_id=prod_real.id,
                    producto_nombre=prod_nombre or (prod_real.nombre if prod_real else ''),
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
                numero_factura = p_data.get('numero_factura')
                if numero_factura:
                    fact_encontrada = Factura.query.filter_by(
                        tienda_id=tienda_id, numero_factura=numero_factura
                    ).first()
                    if fact_encontrada:
                        factura_central_id = fact_encontrada.id

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
                factura_id=factura_central_id, tienda_id=tienda_id,
                fecha=fecha_pago, monto=monto,
                metodo_pago=p_data.get('metodo_pago', 'efectivo'),
                sync_estado='sincronizado', sync_fecha=datetime.utcnow(),
            )
            db.session.add(pago)
            db.session.flush()
            pagos_ok.append(id_local)

            factura_afectada = Factura.query.get(factura_central_id)
            if factura_afectada:
                factura_en_mismo_push = (factura_local_id in mapa_facturas)
                if not factura_en_mismo_push:
                    factura_afectada.valor_pagado = (
                        (factura_afectada.valor_pagado or Decimal('0')) + monto
                    )
                nuevo_saldo_factura = (factura_afectada.saldo_pendiente or Decimal('0')) - monto
                if nuevo_saldo_factura <= 0:
                    nuevo_saldo_factura = Decimal('0')
                    factura_afectada.estado_credito = 'pagado'
                factura_afectada.saldo_pendiente = nuevo_saldo_factura
                factura_afectada.sync_fecha = datetime.utcnow()

                if factura_afectada.cliente_id:
                    nuevo_saldo = (db.session.query(
                        db.func.coalesce(db.func.sum(Factura.saldo_pendiente), 0)
                    ).filter(Factura.cliente_id == factura_afectada.cliente_id).scalar())
                    cliente_afectado = Cliente.query.get(factura_afectada.cliente_id)
                    if cliente_afectado:
                        if nuevo_saldo is None:
                            nuevo_saldo = Decimal('0')
                        if nuevo_saldo < 0:
                            nuevo_saldo = Decimal('0')
                        cliente_afectado.saldo_actual = Decimal(str(nuevo_saldo))
                        cliente_afectado.sync_fecha = datetime.utcnow()
        except Exception as e:
            errores.append(f'Pago {p_data.get("id")}: {e}')

    # ---------- 4. PRODUCTOS ----------
    for p_data in datos.get('productos', []):
        try:
            producto_id = p_data.get('producto_id')
            t_id = p_data.get('tienda_id')
            codigo = p_data.get('codigo_barras')
            nombre = p_data.get('nombre')

            if not t_id:
                continue

            codigo_global = p_data.get('codigo_global')

            # v2.54: matchear primero por codigo_global, después barcode, después nombre
            producto = None
            if codigo_global:
                producto = Producto.query.filter_by(codigo_global=codigo_global).first()
            if not producto and codigo:
                producto = Producto.query.filter_by(codigo_barras=codigo).first()
            if not producto and nombre:
                producto = Producto.query.filter_by(nombre=nombre).first()

            if not producto:
                if not codigo:
                    errores.append(f'Producto {producto_id}: sin codigo_barras, no se puede crear')
                    continue
                try:
                    producto = Producto(
                        nombre=nombre or f'Producto {producto_id}',
                        codigo_barras=codigo,
                        categoria=p_data.get('categoria') or None,
                        codigo_global=codigo_global or str(uuid.uuid4()),
                    )
                    db.session.add(producto)
                    db.session.flush()
                except Exception as e:
                    db.session.rollback()
                    errores.append(f'Producto {producto_id}: no se pudo crear ({e})')
                    continue
            elif codigo_global and not producto.codigo_global:
                # Producto existente sin codigo_global → asignarlo
                producto.codigo_global = codigo_global

            # Categoria
            if producto and p_data.get('categoria') is not None:
                cat_nueva = (p_data.get('categoria') or '').strip()
                if cat_nueva and producto.categoria != cat_nueva:
                    producto.categoria = cat_nueva

            # Nombre (con codigo_global ya no hace falta la guarda vieja)
            if producto and nombre and producto.nombre != nombre:
                producto.nombre = nombre

            # Barcode
            if producto and codigo and producto.codigo_barras != codigo:
                codigo_anterior = producto.codigo_barras
                otro = Producto.query.filter(
                    Producto.codigo_barras == codigo,
                    Producto.id != producto.id
                ).first()
                if otro:
                    errores.append(
                        f'Producto {producto_id}: codigo {codigo} ya existe en "{otro.nombre}"'
                    )
                else:
                    producto.codigo_barras = codigo

            pres = ProductoTienda.query.filter_by(
                producto_id=producto.id, tienda_id=t_id
            ).first()

            if not pres:
                try:
                    pres = ProductoTienda(
                        producto_id=producto.id, tienda_id=t_id, cantidad=0,
                        precio_venta=Decimal('0'), precio_venta1=Decimal('0'),
                        precio_venta2=Decimal('0'), precio_venta3=Decimal('0'),
                    )
                    db.session.add(pres)
                    db.session.flush()
                except Exception as e:
                    db.session.rollback()
                    errores.append(f'Producto {producto_id}: no se pudo crear presentacion ({e})')
                    continue

            # TODOS los campos de ProductoTienda
            pres.cantidad = int(p_data.get('cantidad', pres.cantidad or 0))
            pres.precio_proveedor = Decimal(str(p_data.get('precio_proveedor', pres.precio_proveedor or 0)))
            pres.precio_proveedor2 = Decimal(str(p_data.get('precio_proveedor2', pres.precio_proveedor2 or 0)))
            pres.precio_proveedor3 = Decimal(str(p_data.get('precio_proveedor3', pres.precio_proveedor3 or 0)))
            pres.porcentaje = Decimal(str(p_data.get('porcentaje', pres.porcentaje or 0)))
            pres.precio_venta = Decimal(str(p_data.get('precio_venta', 0)))
            pres.precio_venta1 = Decimal(str(p_data.get('precio_venta1', 0)))
            pres.precio_venta2 = Decimal(str(p_data.get('precio_venta2', 0)))
            pres.precio_venta3 = Decimal(str(p_data.get('precio_venta3', 0)))
            pres.condicion1 = p_data.get('condicion1', '')
            pres.condicion2 = p_data.get('condicion2', '')
            pres.condicion3 = p_data.get('condicion3', '')

            pres.sync_estado = 'sincronizado'
            pres.sync_fecha = datetime.utcnow()

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


# ==================== PULL FACTURAS ====================
def obtener_facturas_para_tienda(tienda_id, desde=None):
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
                'nombre': f.cliente.nombre, 'documento': f.cliente.documento or '',
                'direccion': f.cliente.direccion or '', 'telefono': f.cliente.telefono or '',
                'email': f.cliente.email or '', 'saldo_actual': float(f.cliente.saldo_actual or 0),
            }
        detalles = []
        for d in f.detalles.all():
            detalles.append({
                'producto_id': d.producto_id,
                'codigo_barras': d.producto.codigo_barras if d.producto else '',
                'producto_nombre': d.producto_nombre, 'cantidad': d.cantidad,
                'precio_unitario': float(d.precio_unitario or 0),
                'subtotal': float(d.subtotal or 0),
            })
        resultado.append({
            'id': f.id, 'numero_factura': f.numero_factura, 'tienda_id': f.tienda_id,
            'fecha_hora': f.fecha_hora.isoformat() if f.fecha_hora else None,
            'cliente': cliente_data,
            'usuario_nombre': f.usuario.nombre if f.usuario else None,
            'subtotal': float(f.subtotal or 0), 'total': float(f.total or 0),
            'metodo_pago': f.metodo_pago or '',
            'recargo_nequi': float(f.recargo_nequi or 0),
            'recargo_bolsa': float(f.recargo_bolsa or 0),
            'valor_pagado': float(f.valor_pagado or 0), 'vueltas': float(f.vueltas or 0),
            'tipo_pago': f.tipo_pago or 'contado',
            'estado_credito': f.estado_credito or 'pagado',
            'saldo_pendiente': float(f.saldo_pendiente or 0),
            'precio_manual': bool(getattr(f, 'precio_manual', False)),
            'detalles': detalles,
        })
    return resultado


def marcar_facturas_enviadas(ids):
    if not ids:
        return 0
    n = (Factura.query.filter(Factura.id.in_(ids)).update({
        'origen': 'remota_recibida', 'sync_estado': 'sincronizado',
        'sync_fecha': datetime.utcnow(),
    }, synchronize_session=False))
    db.session.commit()
    return n


def aplicar_facturas_recibidas(tienda_id, facturas):
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
                    tienda_id=tienda_id, nombre=nombre, documento=documento or None,
                    direccion=c_data.get('direccion') or None,
                    telefono=c_data.get('telefono') or None,
                    email=c_data.get('email') or None,
                    saldo_actual=Decimal(str(c_data.get('saldo_actual', 0))),
                    sync_estado='sincronizado', sync_fecha=datetime.utcnow(),
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
                    tienda_id=tienda_id, nombre='Cliente remoto',
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
            numero_factura=numero, tienda_id=tienda_id, fecha_hora=fecha_hora,
            cliente_id=cliente_local_id, usuario_id=None,
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
            sync_estado='sincronizado', sync_fecha=datetime.utcnow(),
        )
        db.session.add(factura)
        db.session.flush()

        for d in f_data.get('detalles', []):
            prod_local = None
            codigo = d.get('codigo_barras') or ''
            nombre_det = d.get('producto_nombre', '')
            if codigo:
                prod_local = Producto.query.filter_by(codigo_barras=codigo).first()
            if not prod_local and nombre_det:
                prod_local = Producto.query.filter_by(nombre=nombre_det).first()
            if not prod_local:
                prod_local = Producto.query.first()
            if not prod_local:
                continue
            detalle = DetalleFactura(
                factura_id=factura.id, producto_id=prod_local.id,
                producto_nombre=nombre_det,
                cantidad=int(d.get('cantidad', 0)),
                precio_unitario=Decimal(str(d.get('precio_unitario', 0))),
                subtotal=Decimal(str(d.get('subtotal', 0))),
            )
            db.session.add(detalle)
        insertadas += 1

    db.session.commit()
    return insertadas


# ==================== HELPERS ====================
def _factura_to_dict_extendida(f):
    return _factura_to_dict(f)


# ==================== PUSH INMEDIATO ====================
def push_factura_individual(tienda_id, factura_id):
    import requests
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
            json=payload, headers={'X-Sync-Key': sync_key}, timeout=8,
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
    import requests
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
            headers={'X-Sync-Key': sync_key}, timeout=15,
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
    """Devuelve TODOS los campos del producto para push."""
    query = ProductoTienda.query.filter_by(
        tienda_id=tienda_id,
        sync_estado='pendiente'
    ).all()

    resultado = []
    for pres in query:
        prod = pres.producto
        resultado.append({
            'producto_id': pres.producto_id,
            'tienda_id': pres.tienda_id,
            'nombre': prod.nombre if prod else None,
            'codigo_barras': prod.codigo_barras if prod else None,
            'codigo_global': prod.codigo_global if prod else None,
            'categoria': prod.categoria if prod else None,
            'cantidad': int(pres.cantidad or 0),
            'precio_proveedor': float(pres.precio_proveedor or 0),
            'precio_proveedor2': float(pres.precio_proveedor2 or 0),
            'precio_proveedor3': float(pres.precio_proveedor3 or 0),
            'porcentaje': float(pres.porcentaje or 0),
            'precio_venta': float(pres.precio_venta or 0),
            'precio_venta1': float(pres.precio_venta1 or 0),
            'precio_venta2': float(pres.precio_venta2 or 0),
            'precio_venta3': float(pres.precio_venta3 or 0),
            'condicion1': pres.condicion1 or '',
            'condicion2': pres.condicion2 or '',
            'condicion3': pres.condicion3 or '',
        })

    return resultado


# ==================== PULL DE PAGOS ====================
def obtener_pagos_para_tienda(tienda_id, desde=None):
    from app.models.pago import Pago
    if isinstance(desde, str) and desde:
        try:
            desde = datetime.fromisoformat(desde.replace('Z', '+00:00'))
        except ValueError:
            desde = None

    query = (
        Pago.query
        .join(Factura, Factura.id == Pago.factura_id)
        .filter(Factura.tienda_id == tienda_id)
        .filter(Pago.sync_estado != 'enviado_tienda')
        .filter(Pago.origen == 'local')
    )
    if desde:
        query = query.filter(Pago.fecha >= desde)
    query = query.order_by(Pago.fecha.asc()).limit(200)
    pagos = query.all()

    resultado = []
    for p in pagos:
        resultado.append({
            'id': p.id, 'factura_id': p.factura_id,
            'numero_factura': p.factura.numero_factura if p.factura else None,
            'tienda_id': p.tienda_id,
            'fecha': p.fecha.isoformat() if p.fecha else None,
            'monto': float(p.monto or 0),
            'metodo_pago': p.metodo_pago or 'efectivo',
        })
    return resultado


def marcar_pagos_enviados_tienda(ids_pagos):
    from app.models.pago import Pago
    if not ids_pagos:
        return 0
    actualizados = (Pago.query.filter(Pago.id.in_(ids_pagos))
                    .update({'sync_estado': 'enviado_tienda'}, synchronize_session=False))
    db.session.commit()
    return actualizados


def aplicar_pagos_recibidos(tienda_id, pagos):
    from app.models.pago import Pago
    insertados = 0
    omitidos = 0
    errores = []

    for p_data in pagos:
        try:
            factura_id = p_data.get('factura_id')
            numero = p_data.get('numero_factura')
            monto = Decimal(str(p_data.get('monto', 0)))

            factura = None
            if numero:
                factura = Factura.query.filter_by(
                    tienda_id=tienda_id, numero_factura=numero
                ).first()
            if not factura:
                errores.append(f'Pago {p_data.get("id")}: factura {numero} no encontrada')
                continue

            existente = Pago.query.filter_by(factura_id=factura.id, monto=monto).first()
            if existente:
                omitidos += 1
                continue

            fecha_str = p_data.get('fecha')
            try:
                fecha_pago = datetime.fromisoformat(fecha_str) if fecha_str else datetime.utcnow()
            except (ValueError, TypeError):
                fecha_pago = datetime.utcnow()

            nuevo_pago = Pago(
                factura_id=factura.id, tienda_id=tienda_id, fecha=fecha_pago,
                monto=monto, metodo_pago=p_data.get('metodo_pago', 'efectivo'),
                origen='remota', sync_estado='sincronizado', sync_fecha=datetime.utcnow(),
            )
            db.session.add(nuevo_pago)

            factura.valor_pagado = (factura.valor_pagado or Decimal('0')) + monto
            nuevo_saldo = (factura.saldo_pendiente or Decimal('0')) - monto
            if nuevo_saldo <= 0:
                nuevo_saldo = Decimal('0')
                factura.estado_credito = 'pagado'
            factura.saldo_pendiente = nuevo_saldo
            factura.sync_fecha = datetime.utcnow()

            if factura.cliente_id:
                nuevo_saldo_cli = (db.session.query(
                    db.func.coalesce(db.func.sum(Factura.saldo_pendiente), 0)
                ).filter(Factura.cliente_id == factura.cliente_id).scalar())
                cli = Cliente.query.get(factura.cliente_id)
                if cli:
                    if nuevo_saldo_cli is None:
                        nuevo_saldo_cli = Decimal('0')
                    if nuevo_saldo_cli < 0:
                        nuevo_saldo_cli = Decimal('0')
                    cli.saldo_actual = Decimal(str(nuevo_saldo_cli))
            insertados += 1
        except Exception as e:
            errores.append(f'Pago {p_data.get("id")}: {e}')

    db.session.commit()
    return insertados, omitidos, errores


# ==================== CONFIGURACION ====================
def _config_to_dict(c):
    return {'id': c.id, 'clave': c.clave, 'valor': c.valor, 'tienda_id': c.tienda_id}


def obtener_config_pendientes_push(tienda_id):
    from app.models.configuracion import Configuracion
    query = Configuracion.query.filter(
        Configuracion.tienda_id.is_(None), Configuracion.sync_estado == 'pendiente',
    ).all()
    return [_config_to_dict(c) for c in query]


def procesar_config_push(tienda_id, configs):
    from app.models.configuracion import Configuracion
    aplicadas = 0
    errores = []
    for c_data in configs:
        clave = (c_data.get('clave') or '').strip()
        valor = c_data.get('valor')
        if not clave or valor is None:
            errores.append(f'Config invalida: {c_data}')
            continue
        try:
            existente = Configuracion.query.filter(
                Configuracion.tienda_id.is_(None), Configuracion.clave == clave,
            ).first()
            if existente:
                if existente.valor != str(valor):
                    existente.valor = str(valor)
            else:
                existente = Configuracion(tienda_id=None, clave=clave, valor=str(valor))
                db.session.add(existente)
            existente.sync_estado = 'pendiente'
            existente.sync_fecha = datetime.utcnow()
            aplicadas += 1
        except Exception as e:
            errores.append(f'Config {clave}: {e}')
    db.session.commit()
    return aplicadas, errores


def obtener_config_para_tienda(tienda_id, desde=None):
    from app.models.configuracion import Configuracion
    query = Configuracion.query.filter(
        Configuracion.tienda_id.is_(None), Configuracion.sync_estado == 'pendiente',
    ).order_by(Configuracion.clave).limit(100)
    return [_config_to_dict(c) for c in query.all()]


def marcar_config_enviada_tienda(ids_configs):
    from app.models.configuracion import Configuracion
    if not ids_configs:
        return 0
    n = (Configuracion.query.filter(Configuracion.id.in_(ids_configs))
         .update({'sync_estado': 'sincronizado', 'sync_fecha': datetime.utcnow()},
                 synchronize_session=False))
    db.session.commit()
    return n


def aplicar_config_recibida(configs):
    from app.models.configuracion import Configuracion
    aplicadas = 0
    ids_aplicados = []
    for c_data in configs:
        clave = (c_data.get('clave') or '').strip()
        valor = c_data.get('valor')
        if not clave or valor is None:
            continue
        existente = Configuracion.query.filter(
            Configuracion.tienda_id.is_(None), Configuracion.clave == clave,
        ).first()
        if existente:
            if existente.valor != str(valor):
                existente.valor = str(valor)
            existente.sync_estado = 'sincronizado'
            existente.sync_fecha = datetime.utcnow()
        else:
            existente = Configuracion(
                tienda_id=None, clave=clave, valor=str(valor),
                sync_estado='sincronizado', sync_fecha=datetime.utcnow(),
            )
            db.session.add(existente)
        ids_aplicados.append(c_data.get('id'))
        aplicadas += 1
    db.session.commit()
    return aplicadas, ids_aplicados