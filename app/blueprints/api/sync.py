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


# ==================== PULL (CENTRAL -> TIENDA) ====================
@bp.route('/sync/pull', methods=['GET'])
@requiere_sync_key
def sync_pull():
    """Devuelve cambios (productos, precios) para que la tienda actualice."""
    from app.services import sync_service

    desde = request.args.get('desde', '')
    datos = sync_service.obtener_cambios_pull(desde)
    return jsonify(datos)


# ==================== PING (HEALTHCHECK) ====================
@bp.route('/sync/ping', methods=['GET'])
def sync_ping():
    """Healthcheck sin autenticacion."""
    return jsonify({
        'ok': True,
        'servidor': 'El Michin Central',
        'hora': datetime.utcnow().isoformat(),
    })