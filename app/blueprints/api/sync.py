# app/blueprints/api/sync.py
from datetime import datetime
from functools import wraps
from flask import request, jsonify, current_app
from . import bp


def requiere_sync_key(f):
    """Decorador: valida el header X-Sync-Key."""
    @wraps(f)
    def decorated(*args, **kwargs):
        expected = current_app.config.get('SYNC_KEY', '')
        provided = request.headers.get('X-Sync-Key', '')
        if not expected or provided != expected:
            return jsonify({'ok': False, 'error': 'Sync key invalida'}), 401
        return f(*args, **kwargs)
    return decorated


# ==================== PUSH (TIENDA -> CENTRAL) ====================
@bp.route('/sync/push', methods=['POST'])
@requiere_sync_key
def sync_push():
    """Recibe datos de una tienda (facturas, pagos, clientes) y los guarda en el central."""
    from app.services import sync_service

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'error': 'Sin datos'}), 400

    tienda_id = data.get('tienda_id')
    if not tienda_id or tienda_id <= 0:
        return jsonify({'ok': False, 'error': 'tienda_id invalido'}), 400

    try:
        resultado = sync_service.procesar_push(tienda_id, data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': f'Error procesando: {e}'}), 500

    return jsonify({
        'ok': True,
        'facturas_ok': resultado.get('facturas_ok', []),
        'pagos_ok': resultado.get('pagos_ok', []),
        'clientes_ok': resultado.get('clientes_ok', []),
        'productos_ok': resultado.get('productos_ok', []),
        'errores': resultado.get('errores', []),
        'recibidas': {
            'facturas': len(resultado.get('facturas_ok', [])),
            'pagos': len(resultado.get('pagos_ok', [])),
            'clientes': len(resultado.get('clientes_ok', [])),
            'productos': len(resultado.get('productos_ok', [])),
        },
    })


# ==================== PULL PRODUCTOS (CENTRAL -> TIENDA) ====================
@bp.route('/sync/pull', methods=['GET'])
@requiere_sync_key
def sync_pull():
    """Devuelve cambios (productos, precios, stock) para una tienda especifica.

    v2.14-fix-ack: si T1 envia header 'X-Sync-Ack: true', NO marcamos los
    productos como sincronizados al servir. T1 confirmara despues via
    /api/sync/ack. Si el header no viene (cliente viejo), marca al servir."""
    from app.services import sync_service

    tienda_id = request.args.get('tienda_id', type=int)
    desde = request.args.get('desde', '')

    if not tienda_id or tienda_id <= 0:
        return jsonify({'ok': False, 'error': 'tienda_id requerido', 'productos': []}), 400

    # v2.14-fix-ack: detectar si el cliente soporta ACK
    soporta_ack = request.headers.get('X-Sync-Ack', '').lower() == 'true'

    datos = sync_service.obtener_cambios_pull(tienda_id, desde)

    # v2.12-fix-A / v2.14-fix-ack: marcar al servir SOLO si el cliente NO usa ACK
    if not soporta_ack:
        ids = [p['producto_id'] for p in datos.get('productos', [])]
        if ids:
            sync_service.marcar_productos_ack(tienda_id, ids)

    return jsonify(datos)


# ==================== ACK DE PULL (TIENDA -> CENTRAL) ====================
@bp.route('/sync/ack', methods=['POST'])
@requiere_sync_key
def sync_ack():
    """v2.14-fix-ack: T1 confirma que aplico N productos del pull.
    Central los marca como sincronizado. Si T1 falla antes de llamar aca,
    los productos siguen 'pendiente' y se reintentan en el proximo ciclo."""
    from app.services import sync_service

    data = request.get_json(silent=True) or {}
    tienda_id = data.get('tienda_id')
    ids_productos = data.get('ids_productos', [])

    if not tienda_id or tienda_id <= 0:
        return jsonify({'ok': False, 'error': 'tienda_id requerido'}), 400

    if not ids_productos:
        return jsonify({'ok': True, 'marcados': 0})

    try:
        marcados = sync_service.marcar_productos_ack(tienda_id, ids_productos)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

    return jsonify({'ok': True, 'marcados': marcados})


# ==================== PULL FACTURAS REMOTAS (CENTRAL -> TIENDA) ====================
@bp.route('/sync/pull-facturas', methods=['GET'])
@requiere_sync_key
def sync_pull_facturas():
    """Devuelve facturas remotas (dueno->tienda) pendientes de enviar."""
    from app.services import sync_service

    tienda_id = request.args.get('tienda_id', type=int)
    desde = request.args.get('desde', '')

    if not tienda_id or tienda_id <= 0:
        return jsonify({'ok': False, 'error': 'tienda_id invalido'}), 400

    try:
        facturas = sync_service.obtener_facturas_para_tienda(tienda_id, desde)
        ids = [f['id'] for f in facturas]
        enviadas = sync_service.marcar_facturas_enviadas(ids)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

    return jsonify({
        'ok': True,
        'tienda_id': tienda_id,
        'total': len(facturas),
        'facturas': facturas,
        'enviadas': enviadas,
        'timestamp': datetime.utcnow().isoformat(),
    })


# ==================== RECUPERAR FACTURA INDIVIDUAL (SIN MARCAR) ====================
@bp.route('/sync/factura/<numero_factura>', methods=['GET'])
@requiere_sync_key
def sync_factura_individual(numero_factura):
    """Devuelve una factura especifica SIN marcarla como enviada."""
    from app.services import sync_service
    from app.models.factura import Factura

    tienda_id = request.args.get('tienda_id', type=int)
    if not tienda_id or tienda_id <= 0:
        return jsonify({'ok': False, 'error': 'tienda_id requerido'}), 400

    factura = Factura.query.filter_by(
        tienda_id=tienda_id, numero_factura=numero_factura
    ).first()

    if not factura:
        return jsonify({'ok': False, 'error': f'Factura {numero_factura} no encontrada'}), 404

    data = sync_service._factura_to_dict_extendida(factura)
    return jsonify({'ok': True, 'factura': data})


# ==================== PING (HEALTHCHECK) ====================
@bp.route('/sync/ping', methods=['GET'])
def sync_ping():
    """Healthcheck sin autenticacion."""
    return jsonify({
        'ok': True,
        'servidor': 'El Michin Central',
        'hora': datetime.utcnow().isoformat(),
    })


# ==================== VERIFICAR FACTURAS FANTASMA ====================
@bp.route('/sync/facturas-existen', methods=['POST'])
@requiere_sync_key
def sync_facturas_existen():
    """Recibe lista de numeros de factura y devuelve cuales existen en central."""
    from app.models.factura import Factura

    data = request.get_json(silent=True) or {}
    tienda_id = data.get('tienda_id')
    numeros = data.get('numeros', [])

    if not tienda_id or not numeros:
        return jsonify({'ok': True, 'existen': [], 'faltan': []})

    resultados = Factura.query.filter(
        Factura.tienda_id == tienda_id,
        Factura.numero_factura.in_(numeros)
    ).with_entities(Factura.numero_factura).all()

    existen = [r[0] for r in resultados]
    faltan = [n for n in numeros if n not in existen]

    return jsonify({
        'ok': True,
        'existen': existen,
        'faltan': faltan,
    })

# ==================== PANEL DE SALUD DEL SYNC (HTML) ====================
@bp.route('/sync/health', methods=['GET'])
def sync_health():
    """v2.14-health: panel de salud del sync en HTML.
    Muestra estado de cada tienda: productos pendientes, ultima sync,
    errores recientes. Solo lectura, sin autenticacion (URL interna)."""
    from app.models.producto import ProductoTienda
    from app.models.sync_log import SyncLog
    from app.models.tienda import Tienda
    from sqlalchemy import func
    from datetime import timedelta

    ahora = datetime.utcnow()
    hace_24h = ahora - timedelta(hours=24)

    # Datos por tienda
    tiendas = Tienda.query.order_by(Tienda.id).all()
    filas_tiendas = []

    for t in tiendas:
        pendientes = (db.session.query(func.count(ProductoTienda.producto_id))
                      .filter(ProductoTienda.tienda_id == t.id,
                              ProductoTienda.sync_estado == 'pendiente')
                      .scalar() or 0)

        ultima_ok = (SyncLog.query
                     .filter_by(tienda_id=t.id, exitoso=True)
                     .order_by(SyncLog.id.desc())
                     .first())

        errores_24h = (SyncLog.query
                       .filter(SyncLog.tienda_id == t.id,
                               SyncLog.exitoso == False,
                               SyncLog.id >= 1)
                       .count())

        hace = '—'
        if ultima_ok and ultima_ok.id:
            # usamos created_at si existe; si no, es aprox
            hace = 'OK'

        filas_tiendas.append({
            'id': t.id,
            'nombre': t.nombre or f'Tienda {t.id}',
            'pendientes': pendientes,
            'errores_24h': errores_24h,
        })

    # Ultimos 15 logs
    logs = (SyncLog.query
            .order_by(SyncLog.id.desc())
            .limit(15)
            .all())

    # Totales globales
    total_productos = (db.session.query(func.count(ProductoTienda.producto_id))
                       .filter(ProductoTienda.tienda_id == 1)
                       .scalar() or 0)
    total_pendientes = (db.session.query(func.count(ProductoTienda.producto_id))
                        .filter(ProductoTienda.tienda_id == 1,
                                ProductoTienda.sync_estado == 'pendiente')
                        .scalar() or 0)

    # ============ HTML ============
    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Salud del Sync - El Michin</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; color: #222; }}
  h1 {{ color: #16a34a; margin: 0 0 20px 0; }}
  h2 {{ color: #444; font-size: 1.1em; margin-top: 30px; border-bottom: 2px solid #ddd; padding-bottom: 8px; }}
  .card {{ background: white; border-radius: 8px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .metrics {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .metric {{ flex: 1; min-width: 150px; background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .metric .valor {{ font-size: 2em; font-weight: bold; color: #16a34a; }}
  .metric .label {{ color: #666; font-size: 0.9em; }}
  .metric.alerta .valor {{ color: #dc2626; }}
  .metric.ok .valor {{ color: #16a34a; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eee; }}
  th {{ background: #fafafa; color: #666; font-size: 0.85em; text-transform: uppercase; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; font-weight: bold; }}
  .badge-ok {{ background: #dcfce7; color: #166534; }}
  .badge-err {{ background: #fee2e2; color: #991b1b; }}
  .badge-warn {{ background: #fef3c7; color: #92400e; }}
  .refresh {{ color: #666; font-size: 0.85em; margin-bottom: 20px; }}
  .refresh a {{ color: #16a34a; text-decoration: none; }}
  .footer {{ color: #999; font-size: 0.8em; margin-top: 30px; }}
</style>
</head>
<body>
<h1>🩺 Salud del Sync — El Michin Central</h1>
<div class="refresh">Actualizado: {ahora.strftime('%Y-%m-%d %H:%M:%S')} UTC · <a href="/api/sync/health">Refrescar</a></div>

<h2>Resumen General</h2>
<div class="metrics">
  <div class="metric">
    <div class="valor">{total_productos}</div>
    <div class="label">Productos totales T1</div>
  </div>
  <div class="metric {'alerta' if total_pendientes > 0 else 'ok'}">
    <div class="valor">{total_pendientes}</div>
    <div class="label">Productos pendientes</div>
  </div>
  <div class="metric">
    <div class="valor">{len(tiendas)}</div>
    <div class="label">Tiendas activas</div>
  </div>
</div>

<h2>Estado por Tienda</h2>
<div class="card">
<table>
<thead><tr><th>ID</th><th>Tienda</th><th>Pendientes</th><th>Errores (24h)</th><th>Estado</th></tr></thead>
<tbody>
'''

    for t in filas_tiendas:
        estado_badge = '<span class="badge badge-ok">OK</span>'
        if t['pendientes'] > 0 or t['errores_24h'] > 5:
            estado_badge = '<span class="badge badge-warn">Revisar</span>'
        if t['errores_24h'] > 20:
            estado_badge = '<span class="badge badge-err">Atención</span>'

        html += f'''<tr>
  <td>{t['id']}</td>
  <td>{t['nombre']}</td>
  <td>{t['pendientes']}</td>
  <td>{t['errores_24h']}</td>
  <td>{estado_badge}</td>
</tr>'''

    html += '''
</tbody>
</table>
</div>

<h2>Últimos 15 logs</h2>
<div class="card">
<table>
<thead><tr><th>ID</th><th>Tienda</th><th>Tipo</th><th>Tabla</th><th>Registros</th><th>OK</th><th>Mensaje</th></tr></thead>
<tbody>
'''

    for l in logs:
        badge = '<span class="badge badge-ok">OK</span>' if l.exitoso else '<span class="badge badge-err">ERROR</span>'
        msg = (l.mensaje or '')[:80]
        html += f'''<tr>
  <td>{l.id}</td>
  <td>{l.tienda_id}</td>
  <td>{l.tipo or ''}</td>
  <td>{l.tabla or ''}</td>
  <td>{l.registros or 0}</td>
  <td>{badge}</td>
  <td>{msg}</td>
</tr>'''

    html += '''
</tbody>
</table>
</div>

<div class="footer">
  Panel de salud v1 — v2.14-health · El Michin
</div>
</body>
</html>'''

    return html