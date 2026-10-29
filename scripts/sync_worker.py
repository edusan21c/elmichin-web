# scripts/sync_worker.py
# Worker de sincronizacion. Corre en cada TIENDA y sincroniza con el central.
# v2.14-backoff: retry exponencial en fallas de push/pull.
# v2.15-alertas: notificaciones por Telegram en fallas consecutivas.
# v2.37-fix-saldo-negativo: sanitizador de clientes con saldo negativo.
# v2.66-fix-paginacion: paginacion por desde_id para evitar 10.000 vueltas.

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


# ==================== NUEVA FUNCION DE AUTO-REPARACION ====================
def reparar_fotos_locales(app):
    """Escanea la carpeta de fotos y las vincula a los productos en la BD si no lo están."""
    from app.models.producto import Producto
    
    with app.app_context():
        try:
            img_dir = os.path.join(RAIZ, 'app', 'static', 'img', 'productos')
            if not os.path.exists(img_dir):
                log('  [Auto-Fix Fotos] Carpeta de productos no encontrada.')
                return

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
                log(f'  [Auto-Fix Fotos] Se vincularon {arregladas} fotos a sus productos correctamente.')
            else:
                log('  [Auto-Fix Fotos] Todas las fotos ya estaban vinculadas.')
        except Exception as e:
            log(f'  [Auto-Fix Fotos] Error: {e}')
            db.session.rollback()
# =======================================================================


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


def corregir_saldos_negativos(app):
    """v2.37-fix-saldo-negativo: red de seguridad."""
    from app.models.cliente import Cliente
    from app.models.factura import Factura

    with app.app_context():
        try:
            negativos = Cliente.query.filter(Cliente.saldo_actual < 0).all()
            if not negativos:
                log('  Sin clientes con saldo negativo')
                return 0

            corregidos = 0
            for c in negativos:
                real = (db.session.query(
                    db.func.coalesce(db.func.sum(Factura.saldo_pendiente), 0)
                ).filter(Factura.cliente_id == c.id).scalar())
                if real is None or real < 0:
                    real = Decimal('0')
                log(f'  FIX saldo cliente {c.id} ({c.nombre}): '
                    f'{c.saldo_actual} -> {real}')
                c.saldo_actual = Decimal(str(real))
                c.sync_fecha = datetime.utcnow()
                corregidos += 1

            db.session.commit()
            log(f'  {corregidos} clientes corregidos')
            return corregidos
        except Exception as e:
            log(f'  Error corregir_saldos_negativos: {e}')
            db.session.rollback()
            return 0


def hacer_push(app, central_url, sync_key, tienda_id):
    """Envia datos pendientes al central."""
    if not puede_intentar('push'):
        return True

    with app.app_context():
        pendientes = sync_service.obtener_pendientes_push(tienda_id)
        productos_pendientes = sync_service.obtener_productos_pendientes_push(tienda_id)
        pendientes['productos'] = productos_pendientes
        config_pendientes = sync_service.obtener_config_pendientes_push(tienda_id)
        pendientes['configuracion'] = config_pendientes

        total = (
            len(pendientes['facturas']) +
            len(pendientes['pagos']) +
            len(pendientes['clientes']) +
            len(pendientes['productos']) +
            len(pendientes['configuracion'])
        )

        if total == 0:
            log('  PUSH: sin cambios pendientes')
            registrar_exito('push')
            return True

        log(f'  PUSH: enviando {total} registros...')
        payload = {'tienda_id': tienda_id, **pendientes}

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
                        tienda_id, 'push', 'mixto', total, True, str(data.get('recibidas', {}))
                    )
                    registrar_exito('push')
                    return True
                else:
                    err = str(data.get('error', 'unknown'))
                    log(f'  PUSH: ERROR - {err}')
                    sync_service.registrar_log(tienda_id, 'push', 'mixto', 0, False, err)
                    registrar_falla('push', err)
                    return False
            else:
                err = f'HTTP {r.status_code}'
                log(f'  PUSH: {err}')
                sync_service.registrar_log(tienda_id, 'push', 'mixto', 0, False, err)
                registrar_falla('push', err)
                return False

        except requests.RequestException as e:
            log(f'  PUSH: fallo de red - {e}')
            registrar_falla('push', f'Red: {e}')
            return False


def hacer_pull(app, central_url, sync_key, tienda_id):
    """Recibe cambios del central (productos Y facturas)."""
    if not puede_intentar('pull'):
        return True

    with app.app_context():
        desde = (datetime.utcnow() - timedelta(days=7)).isoformat()
        headers_pull = {'X-Sync-Key': sync_key, 'X-Sync-Ack': 'true'}
        hubo_error_pull = False
        desde_id = 0  # NUEVO: Paginación

        # ============ 1. PULL PRODUCTOS (en lotes) ============
        log(f'  PULL productos desde {desde[:10]}...')
        total_productos = 0
        ids_pendientes_ack = []
        MAX_ITERACIONES = 50

        for i in range(MAX_ITERACIONES):
            try:
                r = requests.get(
                    central_url.rstrip('/') + '/api/sync/pull',
                    params={'tienda_id': tienda_id, 'desde': desde, 'desde_id': desde_id}, # NUEVO
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
                ultimo_id = datos.get('ultimo_id', desde_id) # NUEVO

                if not productos:
                    break

                # 🛡️ BLINDAJE: Si un producto falla, el robot no se cae
                try:
                    resultado = sync_service.aplicar_cambios_pull({'productos': productos})
                    aplicados = resultado.get('actualizados', 0)
                    ids_lote = resultado.get('ids_aplicados', [])
                except Exception as e:
                    log(f'  [ALERTA] Error aplicando lote {i+1}. Omitiendo productos dañados.')
                    log(f'  Detalle: {e}')
                    db.session.rollback() # Deshacemos el error y seguimos
                    aplicados = 0
                    ids_lote = []
                    
                    # Guardamos el error en un archivo de texto para no perder el rastro
                    try:
                        with open(os.path.join(RAIZ, 'logs', 'errores_productos.txt'), 'a') as f_err:
                            f_err.write(f'[{datetime.now()}] Error en lote {i+1}: {e}\n')
                    except:
                        pass

                total_productos += aplicados
                ids_pendientes_ack.extend(ids_lote)
                desde_id = ultimo_id # NUEVO: actualizar para el siguiente lote SIEMPRE

                log(f'  PULL productos lote {i+1}: {aplicados} actualizados (hay_mas={hay_mas})')

                if not hay_mas:
                    break
            except requests.RequestException as e:
                log(f'  PULL productos: fallo red - {e}')
                hubo_error_pull = True
                break

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

        # ============ 2. PULL CONFIGURACION GLOBAL ============
        try:
            r = requests.get(
                central_url.rstrip('/') + '/api/sync/pull-config',
                params={'tienda_id': tienda_id},
                headers={'X-Sync-Key': sync_key},
                timeout=TIMEOUT_REQUEST,
            )
            if r.status_code == 200:
                datos_conf = r.json()
                configs = datos_conf.get('configuracion', [])
                if configs:
                    aplicadas, ids_conf = sync_service.aplicar_config_recibida(configs)
                    log(f'  PULL config: {aplicadas} aplicadas')
                    if ids_conf:
                        try:
                            requests.post(
                                central_url.rstrip('/') + '/api/sync/marcar-config-enviada',
                                json={'ids_configs': ids_conf},
                                headers={'X-Sync-Key': sync_key},
                                timeout=TIMEOUT_REQUEST,
                            )
                        except requests.RequestException:
                            pass
                else:
                    log('  PULL config: sin cambios')
            else:
                log(f'  PULL config: HTTP {r.status_code}')
                hubo_error_pull = True
        except requests.RequestException as e:
            log(f'  PULL config: fallo red - {e}')
            hubo_error_pull = True

        # ============ 3. PULL FACTURAS REMOTAS ============
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
                    insertadas = sync_service.aplicar_facturas_recibidas(tienda_id, facturas)
                    log(f'  PULL facturas: {insertadas} nuevas (recibidas {len(facturas)})')
                    sync_service.registrar_log(tienda_id, 'pull', 'facturas', insertadas, True, '')
                else:
                    log('  PULL facturas: sin cambios')
            else:
                log(f'  PULL facturas: HTTP {r.status_code}')
                hubo_error_pull = True
        except requests.RequestException as e:
            log(f'  PULL facturas: fallo red - {e}')
            hubo_error_pull = True

        # ============ 4. PULL PAGOS ============
        log(f'  PULL pagos desde {desde[:10]}...')
        try:
            r = requests.get(
                central_url.rstrip('/') + '/api/sync/pull-pagos',
                params={'tienda_id': tienda_id, 'desde': desde},
                headers={'X-Sync-Key': sync_key},
                timeout=TIMEOUT_REQUEST,
            )
            if r.status_code == 200:
                datos = r.json()
                pagos = datos.get('pagos', [])
                if pagos:
                    insertados, omitidos, errores = sync_service.aplicar_pagos_recibidos(tienda_id, pagos)
                    log(f'  PULL pagos: {insertados} nuevos, {omitidos} omitidos, {len(errores)} errores')
                    ids_ok = [p['id'] for p in pagos]
                    if ids_ok:
                        try:
                            requests.post(
                                central_url.rstrip('/') + '/api/sync/marcar-pagos-enviados',
                                json={'tienda_id': tienda_id, 'ids_pagos': ids_ok},
                                headers={'X-Sync-Key': sync_key},
                                timeout=TIMEOUT_REQUEST,
                            )
                        except requests.RequestException:
                            pass
                else:
                    log('  PULL pagos: sin cambios')
            else:
                log(f'  PULL pagos: HTTP {r.status_code}')
                hubo_error_pull = True
        except requests.RequestException as e:
            log(f'  PULL pagos: fallo red - {e}')
            hubo_error_pull = True

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

    log('--- VERIFICACION (facturas fantasma) ---')
    detectar_fantasmas(app, tienda_id)

    log('--- PUSH (enviar pendientes) ---')
    hacer_push(app, central_url, sync_key, tienda_id)

    log('--- PULL (recibir cambios) ---')
    hacer_pull(app, central_url, sync_key, tienda_id)

    log('--- FIX SALDOS NEGATIVOS (v2.37) ---')
    corregir_saldos_negativos(app)

    # NUEVA FUNCION PARA AUTO-REPARAR LAS FOTOS
    log('--- AUTO-REPARACION DE FOTOS ---')
    reparar_fotos_locales(app)

    # --- ACTUALIZACION AUTOMATICA DE ARCHIVOS (v2.88) ---
    log('--- GIT PULL (buscando actualizaciones) ---')
    import subprocess
    try:
        # 1. Traemos los cambios incluyendo las etiquetas (tags)
        r = subprocess.run(['git', 'pull', 'origin', 'main', '--tags'], cwd=RAIZ, capture_output=True, text=True, timeout=60)
        
        # 2. Verificamos si hubo descarga de archivos nuevos
        if 'Fast-forward' in r.stdout or 'files changed' in r.stdout or 'archivos cambiados' in r.stdout:
            log('Git Pull: Se descargaron actualizaciones nuevas.')
            log('REINICIANDO SISTEMA PARA APLICAR CAMBIOS...')
            
            # 3. Reiniciamos el servicio de Flask para que lea el nuevo código
            subprocess.run(['powershell', '-Command', 'Restart-Service MichinFlask -Force'], capture_output=True)
            log('Sistema reiniciado con exito.')
        else:
            log('Git Pull: Sin actualizaciones nuevas.')
    except Exception as e:
        log(f'Git Pull Error: {e}')
    # ----------------------------------------------------

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