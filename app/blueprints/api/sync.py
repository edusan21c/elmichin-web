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
        'facturas_ok': resultado['facturas_ok'],
        'pagos_ok': resultado['pagos_ok'],
        'clientes_ok': resultado['clientes_ok'],
        'errores': resultado['errores'],
        'recibidas': {
            'facturas': len(resultado['facturas_ok']),
            'pagos': len(resultado['pagos_ok']),
            'clientes': len(resultado['clientes_ok']),
        },
    })


# ==================== PULL PRODUCTOS (CENTRAL -> TIENDA) ====================
@bp.route('/sync/pull', methods=['GET'])
@requiere_sync_key
def sync_pull():
    """Devuelve cambios (productos, precios) para que la tienda actualice."""
    from app.services import sync_service

    desde = request.args.get('desde', '')
    datos = sync_service.obtener_cambios_pull(desde)
    return jsonify(datos)


# ==================== PULL FACTURAS REMOTAS (CENTRAL -> TIENDA) ====================
@bp.route('/sync/pull-facturas', methods=['GET'])
@requiere_sync_key
def sync_pull_facturas():
    """
    Devuelve facturas remotas (dueño->tienda) pendientes de enviar.
    Después de servirlas, las marca como 'remota_recibida' para no reenviarlas.
    """
    from app.services import sync_service

    tienda_id = request.args.get('tienda_id', type=int)
    desde = request.args.get('desde', '')

    if not tienda_id or tienda_id <= 0:
        return jsonify({'ok': False, 'error': 'tienda_id invalido'}), 400

    try:
        # 1. Obtener las facturas remotas pendientes
        facturas = sync_service.obtener_facturas_para_tienda(tienda_id, desde)

        # 2. Marcar como enviadas para no reenviarlas en el próximo ciclo
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
    """
    Devuelve una factura específica SIN marcarla como enviada.
    Útil para recuperar facturas que quedaron marcadas como 'remota_recibida'
    por error (por ejemplo, cuando se probó el endpoint desde un navegador).
    """
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
    """Recibe lista de números de factura y devuelve cuáles existen en central."""
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