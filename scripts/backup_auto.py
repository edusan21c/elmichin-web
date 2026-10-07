# scripts/backup_auto.py
# Backup automatico de la BD del central.
# Ejecutar manualmente: python scripts\backup_auto.py
# O programar con Task Scheduler para correr diario.

import os
import sys
import shutil
import subprocess
from datetime import datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(RAIZ, 'backups')
DIAS_RETENCION = 30  # Eliminar backups mayores a 30 dias


def leer_env():
    """Lee las credenciales de la BD desde .env"""
    env_path = os.path.join(RAIZ, '.env')
    config = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    config[key.strip()] = val.strip()
    return config


def hacer_backup():
    """Crea un backup de la BD con pg_dump."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f'Carpeta creada: {BACKUP_DIR}')

    config = leer_env()
    db_name = config.get('DB_NAME', 'michin_central')
    db_user = config.get('DB_USER', 'postgres')
    db_host = config.get('DB_HOST', 'localhost')
    db_port = config.get('DB_PORT', '5432')
    db_password = config.get('DB_PASSWORD', '')

    fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
    archivo = os.path.join(BACKUP_DIR, f'{db_name}_{fecha}.sql')

    print(f'Creando backup: {archivo}')

    # Configurar variable de entorno para no pedir contrasena
    env = os.environ.copy()
    env['PGPASSWORD'] = db_password

    cmd = [
        'pg_dump',
        '-h', db_host,
        '-p', db_port,
        '-U', db_user,
        '-F', 'c',           # formato custom (comprimido)
        '-b',                # incluir blobs grandes
        '-v',                # verbose
        '-f', archivo,
        db_name
    ]

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            size_mb = os.path.getsize(archivo) / (1024 * 1024)
            print(f'OK - Backup creado: {size_mb:.2f} MB')
            return archivo
        else:
            print(f'ERROR: {result.stderr}')
            return None
    except FileNotFoundError:
        print('ERROR: pg_dump no encontrado. Verifica que PostgreSQL este en el PATH.')
        return None


def limpiar_backups_viejos():
    """Elimina backups mayores a DIAS_RETENCION dias."""
    if not os.path.exists(BACKUP_DIR):
        return

    limite = datetime.now() - timedelta(days=DIAS_RETENCION)
    eliminados = 0

    for archivo in os.listdir(BACKUP_DIR):
        if not archivo.endswith('.sql'):
            continue
        ruta = os.path.join(BACKUP_DIR, archivo)
        try:
            # Formato: nombre_db_YYYYMMDD_HHMMSS.sql
            partes = archivo.replace('.sql', '').split('_')
            if len(partes) >= 3:
                fecha_str = f'{partes[-2]}_{partes[-1]}'
                fecha = datetime.strptime(fecha_str, '%Y%m%d_%H%M%S')
                if fecha < limite:
                    os.remove(ruta)
                    eliminados += 1
        except (ValueError, IndexError):
            continue

    if eliminados > 0:
        print(f'Backups eliminados (> {DIAS_RETENCION} dias): {eliminados}')


def enviar_alerta_backup(mensaje):
    """v2.16-backup-alerta: envia alerta Telegram si el backup falla."""
    import urllib.request
    import json as _json

    config = leer_env()
    token = config.get('TELEGRAM_TOKEN', '')
    chat_id = config.get('TELEGRAM_CHAT_ID', '')

    if not token or not chat_id:
        print('[alerta] Telegram no configurado, se omite.')
        return False

    try:
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        payload = _json.dumps({'chat_id': chat_id, 'text': mensaje}).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f'[alerta] No se pudo enviar: {e}')
        return False


def main():
    print('=' * 60)
    print('BACKUP AUTOMATICO - El Michin Central')
    print('=' * 60)
    print()

    archivo = hacer_backup()
    if archivo:
        limpiar_backups_viejos()
        print()
        print('Backup completado correctamente.')
    else:
        print()
        print('Backup FALLO.')
        # v2.16-backup-alerta: notificar por Telegram
        enviar_alerta_backup(
            f'[El Michin Backup] FALLO el backup automatico de la central.\n'
            f'Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M")}\n'
            f'Revisar el log o el estado del servicio PostgreSQL.'
        )
        sys.exit(1)


if __name__ == '__main__':
    main()