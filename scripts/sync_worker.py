# scripts/sync_worker.py
# Worker de sincronizacion. Corre en cada TIENDA y sincroniza con el central.
import os
import sys
import json
import socket
import warnings
from datetime import datetime, timedelta
from decimal import Decimal

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

BACKOFF_MINUTOS = [2, 5, 15, 30, 60]
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
    """v2.15-alertas: envia alerta por Telegram si esta configurado."""
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
    if not os.path.exists(BACKOFF_FILE): return {}
    try:
        with open(BACKOFF_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception: return {}


def _escribir_backoff(data):
    try:
        with open(BACKOFF_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
    except Exception: pass


def puede_intentar(operacion):
    data = _leer_backoff()
    op = data.get(operacion, {})
    proximo = op.get('proximo_intento')
    if not proximo: return True

    try:
        proximo_dt = datetime.fromisoformat(proximo)
        if datetime.now() >= proximo_dt: return True
        restante = int((proximo_dt - datetime.now()).total_seconds() / 60)
        log(f'  {operacion.upper()}: en backoff, faltan {restante} min (fallas: {op.get("fallas", 0)})')
        return False
    except Exception:
        return True


def registrar_exito(operacion):
    data = _leer_backoff()
    data[operacion] = {'fallas': 0, 'proximo_intento': None, 'ultimo_error': None}
    _escribir_backoff(data)


def registrar_falla(operacion, error_msg):
    data = _leer_backoff()
    op = data.get(operacion, {})
    fallas = op.get('fallas', 0) + 1
    idx = min(fallas - 1, len(BACKOFF_MINUTOS) - 1)
    espera_min = BACKOFF_MINUTOS[idx]
    proximo_dt = datetime.now() + timedelta(minutes=espera_min)

    data[operacion] = {
        'fallas': fallas,
        'proximo_intento': proximo_dt.isoformat(),
        'ultimo_error': str(error_msg)[:200],
    }
    _escribir_backoff(data)

    log(f'  {operacion.upper()}: falla {fallas}, proximo intento en {espera_min} min')

    if fallas == UMBRAL_ALERTA_FALLAS:
        try:
            from flask import current_app
            tienda_id = current_app.config.get('TIENDA_ID', '?')
            mensaje = f"[El Michin Alerta]\nWorker de Tienda {tienda_id} con {fallas} fallas en '{operacion}'.\n\nUltimo error: {str(error_msg)[:150]}"
            enviar_alerta_telegram(mensaje)
        except Exception as e:
            log(f'  [alerta] Error al disparar: {e}')


def hay_internet(url):
    try:
        r = requests.get(url.rstrip('/') + '/api/sync/ping', timeout=TIMEOUT_PING)
        return r.status_code == 200
    except requests.RequestException:
        return False


# ==================== NUEVA FUNCION DE AUTO-REPARACION ====================
def reparar_fotos_locales(app):
    from app.models.producto import Producto
    with app.app_context():
        try:
            img_dir = os.path.join(RAIZ, 'app', 'static', 'img', 'productos')
            if not os.path.exists(img_dir): return

            fotos = os.listdir(img_dir)
            arregladas = 0
            for foto in fotos:
                if foto.endswith('.webp'):
                    codigo = foto.replace('.webp', '')
                    prod = Producto.query.filter_by(codigo_barras=codigo).first()
                    if prod and prod.imagen != foto:
                        prod.imagen = foto
                        arregladas += 1

            if arregladas > 0:
                db.session.commit()
                log(f'  [Auto-Fix Fotos] Se vincularon {arregladas} fotos.')
        except Exception as e:
            log(f'  [Auto-Fix Fotos] Error: {e}')
            db.session.rollback()


def detectar_fantasmas(app, tienda_id):
    with app.app_context():
        try:
            faltantes = sync_service.detectar_facturas_faltantes(tienda_id)
            if faltantes > 0: log(f'  {faltantes} facturas re-marcadas')
            else: log('  Sin facturas fantasma')
            return faltantes
        except Exception as e:
            log(f'  Error: {e}')
            return 0


def corregir_saldos_negativos(app):
    from app.models.cliente import Cliente
    from app.models.factura import Factura
    with app.app_context():
        try:
            negativos = Cliente.query.filter(Cliente.saldo_actual < 0).all()
            if not negativos: return 0
            for c in negativos:
                real = (db.session.query(db.func.coalesce(db.func.sum(Factura.saldo_pendiente), 0)).filter(Factura.cliente_id == c.id).scalar())
                if real is None or real < 0: real = Decimal('0')
                c.saldo_actual = Decimal(str(real))
                c.sync_fecha = datetime.utcnow()
            db.session.commit()
            return len(negativos)
        except Exception as e:
            db.session.rollback()
            return 0


def hacer_push(app, central_url, sync_key, tienda_id):
    if not puede_intentar('push'): return True
    with app.app_context():
        pendientes = sync_service.obtener_pendientes_push(tienda_id)
        pendientes['productos'] = sync_service.obtener_productos_pendientes_push(tienda_id)
        pendientes['configuracion'] = sync_service.obtener_config_pendientes_push(tienda_id)

        total = len(pendientes['facturas']) + len(pendientes['pagos']) + len(pendientes['clientes']) + len(pendientes['productos']) + len(pendientes['configuracion'])
        if total == 0:
            registrar_exito('push')
            return True

        try:
            r = requests.post(central_url.rstrip('/') + '/api/sync/push', json={'tienda_id': tienda_id, **pendientes}, headers={'X-Sync-Key': sync_key}, timeout=TIMEOUT_REQUEST)
            if r.status_code == 200 and r.json().get('ok'):
                sync_service.marcar_sincronizados(tienda_id, r.json())
                registrar_exito('push')
                return True
            else:
                registrar_falla('push', f'HTTP {r.status_code}')
                return False
        except requests.RequestException as e:
            registrar_falla('push', f'Red: {e}')
            return False


def hacer_pull(app, central_url, sync_key, tienda_id):
    if not puede_intentar('pull'): return True
    with app.app_context():
        desde = (datetime.utcnow() - timedelta(days=7)).isoformat()
        headers_pull = {'X-Sync-Key': sync_key, 'X-Sync-Ack': 'true'}
        hubo_error_pull = False
        desde_id = 0

        log(f'  PULL productos desde {desde[:10]}...')
        total_productos = 0
        ids_pendientes_ack = []
        MAX_ITERACIONES = 50

        for i in range(MAX_ITERACIONES):
            try:
                r = requests.get(central_url.rstrip('/') + '/api/sync/pull', params={'tienda_id': tienda_id, 'desde': desde, 'desde_id': desde_id}, headers=headers_pull, timeout=TIMEOUT_REQUEST)
                if r.status_code != 200:
                    hubo_error_pull = True
                    break

                datos = r.json()
                productos = datos.get('productos', [])
                hay_mas = datos.get('hay_mas', False)
                ultimo_id = datos.get('ultimo_id', desde_id)

                if not productos:
                    break

                # 🛡️ EL ROBOT YA NO SE CAE AQUÍ GRACIAS AL BLINDAJE DEL SERVICIO
                resultado = sync_service.aplicar_cambios_pull({'productos': productos})
                aplicados = resultado.get('actualizados', 0)
                ids_lote = resultado.get('ids_aplicados', [])

                total_productos += aplicados
                ids_pendientes_ack.extend(ids_lote)
                desde_id = ultimo_id

                log(f'  PULL productos lote {i+1}: {aplicados} actualizados (hay_mas={hay_mas})')

                if not hay_mas:
                    break
            except requests.RequestException as e:
                log(f'  PULL productos: fallo red - {e}')
                hubo_error_pull = True
                break

        if ids_pendientes_ack:
            try:
                requests.post(central_url.rstrip('/') + '/api/sync/ack', json={'tienda_id': tienda_id, 'ids_productos': ids_pendientes_ack}, headers={'X-Sync-Key': sync_key}, timeout=TIMEOUT_REQUEST)
            except requests.RequestException: pass

        # PULL CONFIG
        try:
            r = requests.get(central_url.rstrip('/') + '/api/sync/pull-config', params={'tienda_id': tienda_id}, headers={'X-Sync-Key': sync_key}, timeout=TIMEOUT_REQUEST)
            if r.status_code == 200 and r.json().get('configuracion'):
                aplicadas, ids_conf = sync_service.aplicar_config_recibida(r.json()['configuracion'])
                if ids_conf:
                    requests.post(central_url.rstrip('/') + '/api/sync/marcar-config-enviada', json={'ids_configs': ids_conf}, headers={'X-Sync-Key': sync_key}, timeout=TIMEOUT_REQUEST)
        except requests.RequestException: hubo_error_pull = True

        # PULL FACTURAS
        try:
            r = requests.get(central_url.rstrip('/') + '/api/sync/pull-facturas', params={'tienda_id': tienda_id, 'desde': desde}, headers={'X-Sync-Key': sync_key}, timeout=TIMEOUT_REQUEST)
            if r.status_code == 200 and r.json().get('facturas'):
                sync_service.aplicar_facturas_recibidas(tienda_id, r.json()['facturas'])
        except requests.RequestException: hubo_error_pull = True

        # PULL PAGOS
        try:
            r = requests.get(central_url.rstrip('/') + '/api/sync/pull-pagos', params={'tienda_id': tienda_id, 'desde': desde}, headers={'X-Sync-Key': sync_key}, timeout=TIMEOUT_REQUEST)
            if r.status_code == 200 and r.json().get('pagos'):
                sync_service.aplicar_pagos_recibidos(tienda_id, r.json()['pagos'])
                ids_ok = [p['id'] for p in r.json()['pagos']]
                requests.post(central_url.rstrip('/') + '/api/sync/marcar-pagos-enviados', json={'tienda_id': tienda_id, 'ids_pagos': ids_ok}, headers={'X-Sync-Key': sync_key}, timeout=TIMEOUT_REQUEST)
        except requests.RequestException: hubo_error_pull = True

        if hubo_error_pull: registrar_falla('pull', 'Error en pull')
        else: registrar_exito('pull')
        return total_productos


def main():
    app = create_app()
    with app.app_context():
        tienda_id = app.config.get('TIENDA_ID', 1)
        central_url = app.config.get('CENTRAL_URL', '')
        sync_key = app.config.get('SYNC_KEY', '')

    log('=' * 60)
    log(f'SYNC WORKER - Tienda {tienda_id}')
    log(f'Central: {central_url}')
    log('=' * 60)

    if not central_url or not sync_key:
        log('ERROR: Configuracion incompleta (Central_URL o Sync_Key)')
        sys.exit(1)

    if not hay_internet(central_url):
        log('Sin conexion al central. Reintentando.')
        sys.exit(0)

    log('Conexion al central OK')

    log('--- VERIFICACION (facturas fantasma) ---')
    detectar_fantasmas(app, tienda_id)

    log('--- PUSH (enviar pendientes) ---')
    push_ok = hacer_push(app, central_url, sync_key, tienda_id)

    log('--- PULL (recibir cambios) ---')
    pull_count = hacer_pull(app, central_url, sync_key, tienda_id)

    log('--- FIX SALDOS NEGATIVOS ---')
    corregir_saldos_negativos(app)

    log('--- AUTO-REPARACION DE FOTOS ---')
    reparar_fotos_locales(app)

    log('--- GIT PULL ---')
    import subprocess
    try:
        r = subprocess.run(['git', 'pull', 'origin', 'main', '--tags'], cwd=RAIZ, capture_output=True, text=True, timeout=60)
        if 'Fast-forward' in r.stdout or 'files changed' in r.stdout:
            log('Git Pull: Actualizaciones descargadas. Reiniciando...')
            subprocess.run(['powershell', '-Command', 'Restart-Service MichinFlask -Force'], capture_output=True)
        else:
            log('Git Pull: Sin actualizaciones de código.')
    except Exception as e:
        log(f'Git Error: {e}')

    # --- REPORTE INTELIGENTE A TELEGRAM ---
    try:
        if pull_count and pull_count > 0:
            mensaje = f"🤖 *Reporte Tienda {tienda_id}*\n✅ Sincronización exitosa.\n📦 Productos actualizados: {pull_count}\n⏱ Hora: {datetime.now().strftime('%H:%M:%S')}"
            enviar_alerta_telegram(mensaje)
    except Exception:
        pass

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