# scripts/push_worker.py
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
    # CREATE_NO_WINDOW evita que Git abra ventanas negras en Windows
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    return subprocess.run(['git', *args], cwd=RAIZ, capture_output=True, text=True, timeout=timeout, creationflags=flags)

def main():
    log('--- Ciclo push_worker ---')
    git('config', 'user.email', 'bot@michin.com')
    git('config', 'user.name', 'MichinBot')

    # Traer remoto sin tocar archivos locales
    git('fetch', 'origin', 'main')

    # 1. Ver si hay archivos nuevos modificados
    est = git('status', '--porcelain', 'app/static/img/productos/', 'data/imagenes/')
    
    # 2. Ver si hay commits atascados (locales que no están en GitHub)
    ahead = git('rev-list', '--count', 'origin/main..HEAD')
    commits_pendientes = ahead.stdout.strip() != '0'

    if not est.stdout.strip() and not commits_pendientes:
        log('Sin fotos nuevas ni commits pendientes. Nada que subir.')
        return 0

    # Si hay archivos nuevos sin commitear, los commiteamos
    if est.stdout.strip():
        git('reset', 'HEAD')
        git('add', 'app/static/img/productos/', 'data/imagenes/')
        git('commit', '-m', 'feat: fotos pendientes desde Central (auto)')

    # Push normal
    r = git('push', 'origin', 'main')
    if r.returncode == 0:
        log('Push normal exitoso.')
        return 0

    # Si falla por force, reintentamos
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