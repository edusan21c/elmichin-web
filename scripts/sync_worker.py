# scripts/sync_worker.py
# Worker de sincronizacion. Corre en cada TIENDA y sincroniza con el central.
# Uso: python scripts\sync_worker.py
# O programado con Task Scheduler cada 2 minutos.

import os
import sys
import json
import socket
import warnings
from datetime import datetime, timedelta

import requests

warnings.filterwarnings('ignore', category=UserWarning, module='requests')

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.extensions import db
from app.services import sync_service


# ==================== CONFIGURACION ====================
TIMEOUT_PING = 3
TIMEOUT_REQUEST = 30
LOG_FILE = os.path.join(RAIZ, 'logs', 'sync.log')


def log(msg):
    """Registra mensaje en el log y consola."""
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    linea = f'[{ahora}] {msg}'
    print(linea, flush=True)

    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(linea + '\n')
    except Exception:
        pass


def hay_internet(url):
    """Verifica si el central responde."""
    try:
        r = requests.get(
            url.rstrip('/') + '/api/sync/ping',
            timeout=TIMEOUT_PING
        )
        return r.status_code == 200
    except requests.RequestException:
        return False


def detectar_fantasmas(app, tienda_id):
    """Detecta y re-marca facturas 'sincronizadas' que no existen en central."""
    with app.app_context():
        try:
            faltantes = sync_service.detectar_facturas_faltantes(tienda_id)
            if faltantes > 0:
                log(f'  {faltantes} facturas re-marcadas como pendiente')
            else:
                log('  Sin facturas fantasma')
            return faltantes
        except Exception as e:
            log(f'  Error: {e}')
            return 0


def hacer_push(app, central_url, sync_key, tienda_id):
    """Envia datos pendientes al central (facturas, pagos, clientes, productos)."""
    with app.app_context():
        pendientes = sync_service.obtener_pendientes_push(tienda_id)

        # Agregar productos locales editados (precios/stock)
        productos_pendientes = sync_service.obtener_productos_pendientes_push(tienda_id)
        pendientes['productos'] = productos_pendientes

        total = (
            len(pendientes['facturas']) +
            len(pendientes['pagos']) +
            len(pendientes['clientes']) +
            len(pendientes['productos'])
        )

        if total == 0:
            log('  PUSH: sin cambios pendientes')
            return True

        log(f'  PUSH: enviando {total} registros...')

        payload = {
            'tienda_id': tienda_id,
            **pendientes,
        }

        try:
            r = requests.post(
                central_url.rstrip('/') + '/api/sync/push',
                json=payload,
                headers={'X-Sync-Key': sync_key},
                timeout=TIMEOUT_REQUEST,
            )

            if r.status_code == 200:
                data = r.json()
                if data.get('ok'):
                    sync_service.marcar_sincronizados(tienda_id, data)
                    log(f'  PUSH: OK - {data.get("recibidas", {})}')
                    sync_service.registrar_log(
                        tienda_id, 'push', 'mixto', total,
                        True, str(data.get('recibidas', {}))
                    )
                    return True
                else:
                    log(f'  PUSH: ERROR - {data.get("error")}')
                    sync_service.registrar_log(
                        tienda_id, 'push', 'mixto', 0,
                        False, str(data.get('error'))
                    )
                    return False
            else:
                log(f'  PUSH: HTTP {r.status_code}')
                sync_service.registrar_log(
                    tienda_id, 'push', 'mixto', 0,
                    False, f'HTTP {r.status_code}'
                )
                return False

        except requests.RequestException as e:
            log(f'  PUSH: fallo de red - {e}')
            return False


def hacer_pull(app, central_url, sync_key, tienda_id):
    """Recibe cambios del central (productos Y facturas)."""
    with app.app_context():
        desde = (datetime.utcnow() - timedelta(days=7)).isoformat()

        # ============ 1. PULL PRODUCTOS ============
        log(f'  PULL productos desde {desde[:10]}...')
        try:
            r = requests.get(
                central_url.rstrip('/') + '/api/sync/pull',
                params={'tienda_id': tienda_id, 'desde': desde},
                headers={'X-Sync-Key': sync_key},
                timeout=TIMEOUT_REQUEST,
            )
            if r.status_code == 200:
                datos = r.json()
                productos = datos.get('productos', [])
                if productos:
                    actualizados = sync_service.aplicar_cambios_pull(
                        {'productos': productos}
                    )
                    log(f'  PULL productos: {actualizados} actualizados')
                else:
                    log('  PULL productos: sin cambios')
            else:
                log(f'  PULL productos: HTTP {r.status_code}')
        except requests.RequestException as e:
            log(f'  PULL productos: fallo red - {e}')

        # ============ 2. PULL FACTURAS REMOTAS ============
        log(f'  PULL facturas desde {desde[:10]}...')
        try:
            r = requests.get(
                central_url.rstrip('/') + '/api/sync/pull-facturas',
                params={'tienda_id': tienda_id, 'desde': desde},
                headers={'X-Sync-Key': sync_key},
                timeout=TIMEOUT_REQUEST,
            )
            if r.status_code == 200:
                datos = r.json()
                facturas = datos.get('facturas', [])
                if facturas:
                    insertadas = sync_service.aplicar_facturas_recibidas(
                        tienda_id, facturas
                    )
                    log(f'  PULL facturas: {insertadas} nuevas '
                        f'(recibidas {len(facturas)})')
                    sync_service.registrar_log(
                        tienda_id, 'pull', 'facturas',
                        insertadas, True, ''
                    )
                else:
                    log('  PULL facturas: sin cambios')
            else:
                log(f'  PULL facturas: HTTP {r.status_code}')
        except requests.RequestException as e:
            log(f'  PULL facturas: fallo red - {e}')

        return True


def main():
    """Ciclo principal de sincronizacion."""
    app = create_app()

    with app.app_context():
        tienda_id = app.config.get('TIENDA_ID', 1)
        central_url = app.config.get('CENTRAL_URL', '')
        sync_key = app.config.get('SYNC_KEY', '')

    log('=' * 60)
    log(f'SYNC WORKER - Tienda {tienda_id}')
    log(f'Central: {central_url}')
    log('=' * 60)

    if not central_url:
        log('ERROR: CENTRAL_URL no configurada')
        sys.exit(1)

    if not sync_key:
        log('ERROR: SYNC_KEY no configurada')
        sys.exit(1)

    if not hay_internet(central_url):
        log('Sin conexion al central. Reintentando en el proximo ciclo.')
        sys.exit(0)

    log('Conexion al central OK')

    # ============ VERIFICAR FACTURAS FANTASMA ============
    log('--- VERIFICACION (facturas fantasma) ---')
    detectar_fantasmas(app, tienda_id)

    # PUSH
    log('--- PUSH (enviar pendientes) ---')
    hacer_push(app, central_url, sync_key, tienda_id)

    # PULL
    log('--- PULL (recibir cambios) ---')
    hacer_pull(app, central_url, sync_key, tienda_id)

    log('Ciclo completado.')
    log('')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f'ERROR FATAL: {e}')
        import traceback
        log(traceback.format_exc())
        sys.exit(1)