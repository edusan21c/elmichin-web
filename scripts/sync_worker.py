# scripts/sync_worker.py
# Worker de sincronizacion. Corre en cada TIENDA y sincroniza con el central.
# v2.14-backoff: retry exponencial en fallas de push/pull.
# v2.15-alertas: notificaciones por Telegram en fallas consecutivas.

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
BACKOFF_FILE = os.path.join(RAIZ, '.sync_backoff.json')

# Backoff en minutos segun numero de fallas consecutivas
BACKOFF_MINUTOS = [2, 5, 15, 30, 60]

# v2.15-alertas: umbral de fallas para disparar alerta
UMBRAL_ALERTA_FALLAS = 3


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


# ==================== ALERTAS TELEGRAM ====================
def enviar_alerta_telegram(mensaje):
    """v2.15-alertas: envia alerta por Telegram si esta configurado.
    Lee TELEGRAM_TOKEN y TELEGRAM_CHAT_ID desde el .env (via current_app)."""
    from flask import current_app

    token = current_app.config.get('TELEGRAM_TOKEN', '')
    chat_id = current_app.config.get('TELEGRAM_CHAT_ID', '')

    if not token or not chat_id:
        log('  [alerta] Telegram no configurado, se omite.')
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensaje,
        }
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            log('  [alerta] Telegram enviado OK.')
            return True
        else:
            log(f'  [alerta] Error Telegram HTTP {r.status_code}')
            return False
    except Exception as e:
        log(f'  [alerta] Fallo al enviar: {e}')
        return False


# ==================== BACKOFF ====================
def _leer_backoff():
    """Lee el estado de backoff desde el archivo."""
    if not os.path.exists(BACKOFF_FILE):
        return {}
    try:
        with open(BACKOFF_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _escribir_backoff(data):
    """Escribe el estado de backoff al archivo."""
    try:
        with open(BACKOFF_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def puede_intentar(operacion):
    """v2.14-backoff: verifica si ya paso el tiempo de espera."""
    data = _leer_backoff()
    op = data.get(operacion, {})
    proximo = op.get('proximo_intento')

    if not proximo:
        return True

    try:
        proximo_dt = datetime.fromisoformat(proximo)
        if datetime.now() >= proximo_dt:
            return True
        restante = int((proximo_dt - datetime.now()).total_seconds() / 60)
        log(f'  {operacion.upper()}: en backoff, faltan {restante} min '
            f'(fallas consecutivas: {op.get("fallas", 0)})')
        return False
    except Exception:
        return True


def registrar_exito(operacion):
    """v2.14-backoff: resetea el contador de fallas."""
    data = _leer_backoff()
    data[operacion] = {
        'fallas': 0,
        'proximo_intento': None,
        'ultimo_error': None,
    }
    _escribir_backoff(data)


def registrar_falla(operacion, error_msg):
    """v2.14-backoff: incrementa fallas y programa proximo intento.
    v2.15-alertas: dispara alerta Telegram en el umbral."""
    data = _leer_backoff()
    op = data.get(operacion, {})
    fallas_previas = op.get('fallas', 0)
    fallas = fallas_previas + 1

    # Indice del backoff (maximo el ultimo de la lista)
    idx = min(fallas - 1, len(BACKOFF_MINUTOS) - 1)
    espera_min = BACKOFF_MINUTOS[idx]

    proximo_dt = datetime.now() + timedelta(minutes=espera_min)

    data[operacion] = {
        'fallas': fallas,
        'proximo_intento': proximo_dt.isoformat(),
        'ultimo_error': str(error_msg)[:200],
    }
    _escribir_backoff(data)

    log(f'  {operacion.upper()}: falla {fallas} registrada, '
        f'proximo intento en {espera_min} min')

    # v2.15-alertas: disparar alerta cuando alcanza el umbral exacto
    if fallas == UMBRAL_ALERTA_FALLAS:
        try:
            from flask import current_app
            tienda_id = current_app.config.get('TIENDA_ID', '?')
            mensaje = (
                f"[El Michin Alerta]\n"
                f"Worker de Tienda {tienda_id} con {fallas} fallas consecutivas "
                f"en operacion '{operacion}'.\n\n"
                f"Ultimo error: {str(error_msg)[:150]}\n\n"
                f"Revisar el estado de la red o la central."
            )
            enviar_alerta_telegram(mensaje)
        except Exception as e:
            log(f'  [alerta] Error al disparar: {e}')


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
    """Envia datos pendientes al central (facturas, pagos, clientes, productos).
    v2.14-backoff: salta si esta en periodo de espera."""
    if not puede_intentar('push'):
        return True

    with app.app_context():
        pendientes = sync_service.obtener_pendientes_push(tienda_id)

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
            registrar_exito('push')
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
                    registrar_exito('push')
                    return True
                else:
                    err = str(data.get('error', 'unknown'))
                    log(f'  PUSH: ERROR - {err}')
                    sync_service.registrar_log(
                        tienda_id, 'push', 'mixto', 0,
                        False, err
                    )
                    registrar_falla('push', err)
                    return False
            else:
                err = f'HTTP {r.status_code}'
                log(f'  PUSH: {err}')
                sync_service.registrar_log(
                    tienda_id, 'push', 'mixto', 0,
                    False, err
                )
                registrar_falla('push', err)
                return False

        except requests.RequestException as e:
            log(f'  PUSH: fallo de red - {e}')
            registrar_falla('push', f'Red: {e}')
            return False


def hacer_pull(app, central_url, sync_key, tienda_id):
    """Recibe cambios del central (productos Y facturas).
    v2.14-pull-lotes: itera en lotes de 200.
    v2.14-fix-ack: envia header X-Sync-Ack y confirma cada lote aplicado.
    v2.14-backoff: salta si esta en periodo de espera.
    v2.15-alertas: alerta en fallas consecutivas."""
    if not puede_intentar('pull'):
        return True

    with app.app_context():
        desde = (datetime.utcnow() - timedelta(days=7)).isoformat()

        headers_pull = {
            'X-Sync-Key': sync_key,
            'X-Sync-Ack': 'true',
        }

        # ============ 1. PULL PRODUCTOS (en lotes) ============
        log(f'  PULL productos desde {desde[:10]}...')
        total_productos = 0
        ids_pendientes_ack = []
        MAX_ITERACIONES = 50
        hubo_error_pull = False

        for i in range(MAX_ITERACIONES):
            try:
                r = requests.get(
                    central_url.rstrip('/') + '/api/sync/pull',
                    params={'tienda_id': tienda_id, 'desde': desde},
                    headers=headers_pull,
                    timeout=TIMEOUT_REQUEST,
                )
                if r.status_code != 200:
                    log(f'  PULL productos: HTTP {r.status_code}')
                    hubo_error_pull = True
                    break

                datos = r.json()
                productos = datos.get('productos', [])
                hay_mas = datos.get('hay_mas', False)

                if not productos:
                    break

                resultado = sync_service.aplicar_cambios_pull(
                    {'productos': productos}
                )
                aplicados = resultado.get('actualizados', 0)
                ids_lote = resultado.get('ids_aplicados', [])

                total_productos += aplicados
                ids_pendientes_ack.extend(ids_lote)

                log(f'  PULL productos lote {i+1}: {aplicados} '
                    f'actualizados (hay_mas={hay_mas})')

                if not hay_mas:
                    break
            except requests.RequestException as e:
                log(f'  PULL productos: fallo red - {e}')
                hubo_error_pull = True
                break

        # v2.14-fix-ack: enviar ACK al central con todos los IDs aplicados
        if ids_pendientes_ack:
            try:
                r = requests.post(
                    central_url.rstrip('/') + '/api/sync/ack',
                    json={'tienda_id': tienda_id, 'ids_productos': ids_pendientes_ack},
                    headers={'X-Sync-Key': sync_key},
                    timeout=TIMEOUT_REQUEST,
                )
                if r.status_code == 200:
                    data = r.json()
                    log(f'  ACK productos: {data.get("marcados", 0)} marcados en central')
                else:
                    log(f'  ACK productos: HTTP {r.status_code} (se reintentaran)')
            except requests.RequestException as e:
                log(f'  ACK productos: fallo red - {e} (se reintentaran)')

        if total_productos > 0:
            log(f'  PULL productos TOTAL: {total_productos} actualizados')
        else:
            log('  PULL productos: sin cambios')

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
                hubo_error_pull = True
        except requests.RequestException as e:
            log(f'  PULL facturas: fallo red - {e}')
            hubo_error_pull = True

        # v2.14-backoff: registrar exito o falla
        if hubo_error_pull:
            registrar_falla('pull', 'Error en algun paso del pull')
        else:
            registrar_exito('pull')

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