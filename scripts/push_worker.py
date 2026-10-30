# scripts/push_worker.py
# Worker de subida de fotos a GitHub. Corre en la CENTRAL.
# Diseñado para ejecutarse UNA vez por ciclo (Programador de Tareas cada 2 min).
import os
import subprocess
import sys
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(RAIZ, 'logs', 'push_worker.log')

def log(msg):
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    linea = f'[{ahora}] {msg}'
    print(linea, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(linea + '\n')
    except Exception:
        pass

def git(*args, timeout=180):
    return subprocess.run(['git', *args], cwd=RAIZ, capture_output=True, text=True, timeout=timeout)

def main():
    log('--- Ciclo push_worker ---')
    git('config', 'user.email', 'bot@michin.com')
    git('config', 'user.name', 'MichinBot')

    # Ver si hay algo que subir SOLO en las carpetas de fotos
    est = git('status', '--porcelain', 'app/static/img/productos/', 'data/imagenes/')
    if not est.stdout.strip():
        log('Sin fotos nuevas. Nada que subir.')
        return 0

    # Traer remoto sin tocar archivos locales
    git('fetch', 'origin', 'main')

    # Desmarcar lo que estuviera en staging y dejar SOLO las fotos
    git('reset', 'HEAD')
    git('add', 'app/static/img/productos/', 'data/imagenes/')

    # Commit (si no hay nada, no es error)
    git('commit', '-m', 'feat: fotos pendientes desde Central (auto)')

    # 1er intento: push normal (seguro)
    r = git('push', 'origin', 'main')
    if r.returncode == 0:
        log('Push normal exitoso.')
        return 0

    # Si rechazó por non-fast-forward, reintentar con --force (igual que antes)
    err = (r.stderr or '') + (r.stdout or '')
    if 'non-fast-forward' in err or 'rejected' in err or 'fetch first' in err:
        log('Push normal rechazado. Reintentando con --force...')
        r2 = git('push', 'origin', 'main', '--force')
        if r2.returncode == 0:
            log('Push forzado exitoso.')
            return 0
        log(f'ERROR push forzado: {r2.stderr}')
        return 1

    log(f'ERROR push: {r.stderr}')
    return 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        log(f'ERROR FATAL: {e}')
        sys.exit(1)