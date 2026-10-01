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


@bp.route('/sync/push', methods=['POST'])
@requiere_sync_key
def sync_push():
    """Recibe datos de una tienda (facturas, pagos, clientes)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'error': 'Sin datos'}), 400

    tienda_id = data.get('tienda_id')
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'Falta tienda_id'}), 400

    facturas = data.get('facturas', [])
    pagos = data.get('pagos', [])
    clientes = data.get('clientes', [])

    resultado = {
        'ok': True,
        'facturas_ok': [f['id'] for f in facturas],
        'pagos_ok': [p['id'] for p in pagos],
        'clientes_ok': [c['id'] for c in clientes],
        'recibidas': {
            'facturas': len(facturas),
            'pagos': len(pagos),
            'clientes': len(clientes),
        }
    }
    return jsonify(resultado)


@bp.route('/sync/pull', methods=['GET'])
@requiere_sync_key
def sync_pull():
    """Devuelve cambios (productos, precios) para que la tienda actualice."""
    from app.services import sync_service  # IMPORT DIFERIDO
    desde = request.args.get('desde', '')
    datos = sync_service.obtener_cambios_pull(desde)
    return jsonify(datos)


@bp.route('/sync/ping', methods=['GET'])
def sync_ping():
    """Healthcheck sin autenticacion."""
    return jsonify({
        'ok': True,
        'servidor': 'El Michin Central',
        'hora': datetime.utcnow().isoformat(),
    })