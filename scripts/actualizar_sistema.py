# scripts/actualizar_sistema.py
# Script que hace la actualizacion completa del sistema.
# Es lanzado por el servicio Flask como subprocess separado.

import os
import sys
import json
import time
import subprocess
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVO_ESTADO = os.path.join(RAIZ, '.update_status.json')
ARCHIVO_LOG = os.path.join(RAIZ, 'logs', 'update.log')
NOMBRE_SERVICIO = 'MichinFlask'

# Scripts de migración manual que se corren en cada actualización.
# Cada uno debe ser idempotente (si ya está aplicado, no rompe).
# Se ejecutan en orden.
MIGRACIONES_MANUALES = [
    'agregar_origen.py',
    'agregar_precio_manual.py',
]


def log(msg):
    """Registra en consola y en archivo."""
    linea = f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
    print(linea, flush=True)
    try:
        os.makedirs(os.path.dirname(ARCHIVO_LOG), exist_ok=True)
        with open(ARCHIVO_LOG, 'a', encoding='utf-8') as f:
            f.write(linea + '\n')
    except Exception:
        pass


def guardar_estado(paso, progreso, estado='en_progreso', mensaje=''):
    """Escribe el estado actual para que el frontend lo lea."""
    try:
        with open(ARCHIVO_ESTADO, 'w', encoding='utf-8') as f:
            json.dump({
                'estado': estado,
                'paso': paso,
                'progreso': progreso,
                'mensaje': mensaje,
                'fecha': datetime.now().isoformat(),
            }, f)
    except Exception as e:
        log(f'Error guardando estado: {e}')


def ejecutar(comando, cwd=None, timeout=300):
    """Ejecuta un comando y devuelve (ok, stdout, stderr)."""
    try:
        result = subprocess.run(
            comando,
            cwd=cwd or RAIZ,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=isinstance(comando, str),
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, '', f'Timeout ejecutando: {comando}'
    except Exception as e:
        return False, '', str(e)


def reiniciar_servicio():
    """Reinicia el servicio de Windows."""
    ok, _, err = ejecutar(f'net stop {NOMBRE_SERVICIO}', timeout=30)
    if not ok:
        log(f'Aviso deteniendo servicio: {err}')

    time.sleep(2)

    ok, _, err = ejecutar(f'net start {NOMBRE_SERVICIO}', timeout=30)
    if not ok:
        log(f'Error iniciando servicio: {err}')
        return False

    return True


def correr_migraciones_manuales(python_exe):
    """Corre los scripts de migración manual en orden. Idempotentes."""
    for nombre_script in MIGRACIONES_MANUALES:
        ruta = os.path.join(RAIZ, 'scripts', nombre_script)
        if not os.path.exists(ruta):
            log(f'  ({nombre_script} no existe, saltando)')
            continue

        log(f'  -> python scripts/{nombre_script}')
        ok, out, err = ejecutar([python_exe, ruta], timeout=120)

        if ok:
            log(f'  OK {nombre_script}')
            # Loguear las líneas relevantes del output
            for linea in (out or '').splitlines():
                if any(k in linea for k in ('===', '✅', '⚠️', 'MIGRACIÓN', '📊')):
                    log(f'     {linea.strip()}')
        else:
            log(f'  Aviso en {nombre_script}: {(err or "")[:200]}')
            # No es fatal: si el script no aplica, no rompe el sistema


def main():
    log('=' * 60)
    log('INICIANDO ACTUALIZACION DEL SISTEMA')
    log('=' * 60)

    # Esperar para que el HTTP response del endpoint termine
    time.sleep(2)

    # ============ 1. GIT PULL ============
    guardar_estado('Descargando cambios de GitHub...', 10)
    log('[1/5] git pull origin main')

    ok, out, err = ejecutar('git pull origin main', timeout=120)
    if not ok:
        log(f'ERROR en git pull: {err}')
        guardar_estado('Error en git pull', 10, 'error', err[:200])
        return

    log(f'git pull OK: {out.strip()[:200]}')

    # ============ 2. PIP INSTALL ============
    guardar_estado('Instalando dependencias...', 30)
    log('[2/5] pip install -r requirements.txt')

    python_exe = os.path.join(RAIZ, 'venv', 'Scripts', 'python.exe')
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    ok, out, err = ejecutar(
        [python_exe, '-m', 'pip', 'install', '-r', 'requirements.txt', '--quiet'],
        timeout=300,
    )
    if not ok:
        log(f'Aviso en pip install: {err}')
        # No es fatal, continuamos

    # ============ 3. FLASK DB UPGRADE ============
    guardar_estado('Aplicando cambios a la base de datos...', 55)
    log('[3/5] flask db upgrade')

    ok, out, err = ejecutar(
        [python_exe, '-m', 'flask', 'db', 'upgrade'],
        timeout=120,
    )
    if not ok:
        log(f'Aviso en flask db upgrade: {err}')
        # No es fatal, continuamos

    # ============ 3.5. MIGRACIONES ADICIONALES (idempotentes) ============
    # Corre scripts de migración manual que agregan columnas/tablas.
    # Cada script es idempotente: si ya está aplicado, no rompe.
    guardar_estado('Aplicando migraciones adicionales...', 70)
    log('[3.5/5] Migraciones manuales')
    correr_migraciones_manuales(python_exe)

    # ============ 4. REINICIAR SERVICIO ============
    guardar_estado('Reiniciando servicio...', 90)
    log('[4/5] Reiniciando servicio Flask')

    ok = reiniciar_servicio()
    if not ok:
        log('ERROR reiniciando servicio')
        guardar_estado('Error reiniciando servicio', 90, 'error')
        return

    # ============ FIN ============
    log('ACTUALIZACION COMPLETADA')
    guardar_estado('Actualizacion completada', 100, 'completado', 'Sistema actualizado correctamente')

    # Esperar un poco y limpiar estado
    time.sleep(30)
    try:
        if os.path.exists(ARCHIVO_ESTADO):
            os.remove(ARCHIVO_ESTADO)
    except Exception:
        pass


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f'ERROR FATAL: {e}')
        import traceback
        log(traceback.format_exc())
        guardar_estado('Error fatal', 0, 'error', str(e)[:200])