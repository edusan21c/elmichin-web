# app/blueprints/reportes/routes.py
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from . import bp
from app.extensions import db
from app.models.tienda import Tienda
from app.models.cliente import Cliente
from app.models.factura import Factura, DetalleFactura
from app.models.pago import Pago


def hora_local():
    return datetime.utcnow() - timedelta(hours=5)


def tienda_actual():
    if current_user.es_programador():
        tid = request.args.get('tienda', type=int)
        if tid:
            return tid
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None
    return current_user.tienda_id


def redondear(v):
    return Decimal(str(v or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ==================== VENTAS ====================
@bp.route('/')
@bp.route('/ventas')
@login_required
def ventas():
    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()

    # Filtros
    desde_str = request.args.get('desde', '', type=str).strip()
    hasta_str = request.args.get('hasta', '', type=str).strip()
    q = request.args.get('q', '', type=str).strip()

    hoy = hora_local().date()
    if not desde_str:
        desde_str = hoy.strftime('%Y-%m-%d')
    if not hasta_str:
        hasta_str = hoy.strftime('%Y-%m-%d')

    try:
        # Los rangos son fechas LOCALES (Colombia UTC-5)
        # El central guarda en UTC, así que sumamos 5h para convertir a UTC
        desde = datetime.strptime(desde_str, '%Y-%m-%d') + timedelta(hours=5)
        hasta = datetime.strptime(hasta_str, '%Y-%m-%d') + timedelta(days=1, hours=5)
    except ValueError:
        desde = datetime.combine(hoy, datetime.min.time()) + timedelta(hours=5)
        hasta = desde + timedelta(days=1)

    # Query base
    query = Factura.query.filter(
        Factura.tienda_id == tienda_id,
        Factura.fecha_hora >= desde,
        Factura.fecha_hora < hasta
    )

    if q:
        query = query.join(Cliente).filter(
            or_(
                Factura.numero_factura.ilike(f'%{q}%'),
                Cliente.nombre.ilike(f'%{q}%')
            )
        )

    facturas = query.order_by(Factura.fecha_hora.desc()).limit(500).all()

    # Totales del periodo (usando mismo rango UTC)
    total_periodo = db.session.query(func.coalesce(func.sum(Factura.total), 0)).filter(
        Factura.tienda_id == tienda_id,
        Factura.fecha_hora >= desde,
        Factura.fecha_hora < hasta
    ).scalar() or 0

    num_facturas = len(facturas)
    ticket_promedio = float(total_periodo) / num_facturas if num_facturas > 0 else 0

    return render_template(
        'reportes/ventas.html',
        facturas=facturas,
        tiendas=tiendas,
        tienda_id=tienda_id,
        desde=desde_str,
        hasta=hasta_str,
        q=q,
        total_periodo=float(total_periodo),
        num_facturas=num_facturas,
        ticket_promedio=ticket_promedio,
    )


# ==================== DETALLE DE FACTURA ====================
@bp.route('/<int:factura_id>')
@login_required
def detalle(factura_id):
    from app.models.configuracion import Configuracion
    
    factura = Factura.query.get_or_404(factura_id)
    detalles = DetalleFactura.query.filter_by(factura_id=factura_id).all()
    pagos = Pago.query.filter_by(factura_id=factura_id).order_by(Pago.fecha.desc()).all()

    # Obtener % recargo de config
    conf = Configuracion.query.filter(
        Configuracion.clave == 'recargo_nequi',
        Configuracion.tienda_id.is_(None)
    ).first()
    recargo_porcentaje = float(conf.valor) if conf else 0.4

    return render_template(
        'reportes/detalle.html',
        factura=factura,
        detalles=detalles,
        pagos=pagos,
        cliente=factura.cliente,
        recargo_porcentaje=recargo_porcentaje,
    )


# ==================== CUENTAS POR COBRAR ====================
@bp.route('/cuentas-por-cobrar')
@login_required
def cuentas_por_cobrar():
    tienda_id = tienda_actual()
    tiendas = Tienda.query.filter_by(activa=True).all()

    clientes_deuda = (Cliente.query
                      .filter(Cliente.tienda_id == tienda_id,
                              Cliente.saldo_actual > 0.01)
                      .order_by(Cliente.saldo_actual.desc())
                      .all())

    total_deuda = sum(float(c.saldo_actual or 0) for c in clientes_deuda)

    return render_template(
        'reportes/cuentas_por_cobrar.html',
        clientes=clientes_deuda,
        tiendas=tiendas,
        tienda_id=tienda_id,
        total_deuda=total_deuda,
    )


# ==================== API: FACTURAS PENDIENTES DE UN CLIENTE ====================
@bp.route('/api/cliente/<int:cliente_id>/pendientes')
@login_required
def api_facturas_pendientes(cliente_id):
    facturas = (Factura.query
                .filter_by(cliente_id=cliente_id)
                .filter(Factura.estado_credito == 'pendiente',
                        Factura.saldo_pendiente > 0.01)
                .order_by(Factura.fecha_hora.asc())
                .all())

    return jsonify([{
        'id': f.id,
        'numero': f.numero_factura,
        'fecha': (f.fecha_hora - timedelta(hours=5)).strftime('%d/%m/%Y'),
        'total': float(f.total or 0),
        'saldo': float(f.saldo_pendiente or 0),
    } for f in facturas])


# ==================== REGISTRAR ABONO ====================
@bp.route('/abono', methods=['POST'])
@login_required
def registrar_abono():
    from app.models.configuracion import Configuracion

    factura_id = request.form.get('factura_id', type=int)
    monto = request.form.get('monto', type=float)
    metodo = request.form.get('metodo', 'efectivo', type=str)
    aplicar_recargo = request.form.get('aplicar_recargo') == 'on'
    recibido = request.form.get('recibido', type=float)

    if not factura_id or not monto or monto <= 0:
        flash('Datos inválidos', 'danger')
        return redirect(url_for('reportes.cuentas_por_cobrar'))

    factura = Factura.query.get_or_404(factura_id)
    if factura.estado_credito != 'pendiente' or factura.saldo_pendiente <= 0:
        flash('Esta factura no tiene saldo pendiente', 'warning')
        return redirect(url_for('reportes.cuentas_por_cobrar'))

    saldo_actual = float(factura.saldo_pendiente)

    # Cap automático: si el monto supera el saldo, se ajusta
    if monto > saldo_actual + 0.01:
        flash(f'Monto ajustado al saldo pendiente (${saldo_actual:,.0f}).', 'info')
        monto = saldo_actual

    # Redondear al saldo exacto si está muy cerca
    if abs(monto - saldo_actual) < 0.10:
        monto = saldo_actual

    monto_base = redondear(monto)

    # Calcular recargo digital
    recargo = Decimal('0')
    if metodo in ('nequi', 'daviplata') and aplicar_recargo:
        conf = Configuracion.query.filter(
            Configuracion.clave == 'recargo_nequi',
            Configuracion.tienda_id.is_(None)
        ).first()
        porcentaje = Decimal(conf.valor) if conf else Decimal('0.4')
        recargo = redondear(monto_base * (porcentaje / Decimal('100')))

    total_cobrado = monto_base + recargo

    # Calcular vueltas si el cliente dio más
    vueltas = Decimal('0')
    if recibido and recibido > 0:
        recibido_dec = redondear(recibido)
        if recibido_dec > total_cobrado:
            vueltas = redondear(recibido_dec - total_cobrado)

    # Crear pago con recargo
    pago = Pago(
        factura_id=factura.id,
        tienda_id=factura.tienda_id,
        monto=monto_base,
        recargo=recargo,
        metodo_pago=metodo,
    )
    db.session.add(pago)

    # Actualizar factura
    nuevo_saldo = redondear(Decimal(str(saldo_actual)) - monto_base)
    factura.saldo_pendiente = nuevo_saldo
    if nuevo_saldo <= 0.01:
        factura.estado_credito = 'pagado'
        factura.saldo_pendiente = Decimal('0')

    # Actualizar cliente
    cliente = factura.cliente
    cliente.saldo_actual = redondear(
        Decimal(str(cliente.saldo_actual or 0)) - monto_base
    )

    db.session.commit()

    # Mensaje con desglose
    msg = f'Abono de ${float(monto_base):,.0f}'
    if recargo > 0:
        msg += f' + recargo ${float(recargo):,.0f}'
    msg += f'. Nuevo saldo: ${float(factura.saldo_pendiente):,.0f}'
    if vueltas > 0:
        msg += f'. Vueltas: ${float(vueltas):,.0f}'
    flash(msg, 'success')

    return redirect(url_for('reportes.detalle', factura_id=factura.id))