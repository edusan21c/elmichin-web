# app/services/updater_service.py
"""Servicio de actualizacion automatica desde GitHub."""
import os
import subprocess
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_GITHUB = 'edusan21c/elmichin-web'
API_TAGS = f'https://api.github.com/repos/{REPO_GITHUB}/tags'
ARCHIVO_ESTADO = os.path.join(RAIZ, '.update_status.json')
NOMBRE_TAREA = 'MichinUpdate'


# ==================== VERSION LOCAL ====================
def get_version_local():
    """Obtiene la version actual. Lee git tag o version.py."""
    # Intentar con git describe
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            if version.startswith('v'):
                return version
    except Exception:
        pass

    # Fallback a version.py
    try:
        sys.path.insert(0, RAIZ)
        from version import VERSION
        return f'v{VERSION}'
    except Exception:
        return 'v0.0'


# ==================== VERSION REMOTA (GITHUB) ====================
def get_versions_remotas():
    """Consulta los tags disponibles en GitHub."""
    try:
        req = urllib.request.Request(
            API_TAGS,
            headers={'User-Agent': 'ElMichin-Updater'},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            # Extrae solo los nombres de tags que empiezan con 'v'
            versiones = [t['name'] for t in data if t['name'].startswith('v')]
            return versiones
    except urllib.error.URLError as e:
        raise Exception(f'Sin conexion a GitHub: {e}')
    except Exception as e:
        raise Exception(f'Error consultando GitHub: {e}')


def get_ultima_version_remota():
    """Devuelve el tag mas reciente."""
    versiones = get_versions_remotas()
    if not versiones:
        return None
    # Ordenar por version (formato vX.Y[.Z] o vX.Y-sufijo)
    return sorted(versiones, key=parse_version, reverse=True)[0]


def parse_version(v):
    """Convierte 'v2.14-pull-lotes' en tupla (2, 14) para comparar.

    v2.14-updater-fix: ignora sufijos despues del numero. Antes, cuando
    el sufijo existia (ej: 'v2.14-pull-lotes'), el int() fallaba y ponia 0,
    causando que (2,0) fuera menor que (2,11) y que v2.11 pareciera mas
    nueva que las versiones con sufijo.
    """
    v = v.lstrip('v')
    partes = []
    for p in v.split('.'):
        # Extrae solo los digitos iniciales de cada parte
        # Ej: '14-pull-lotes' -> '14' | '11' -> '11' | '1fix' -> '1'
        num = ''
        for c in p:
            if c.isdigit():
                num += c
            else:
                break
        try:
            partes.append(int(num) if num else 0)
        except ValueError:
            partes.append(0)
    return tuple(partes)


def hay_actualizacion():
    """Compara la version local con la ultima remota."""
    try:
        local = get_version_local()
        remota = get_ultima_version_remota()
        if not remota:
            return False, local, None
        return parse_version(remota) > parse_version(local), local, remota
    except Exception:
        local = get_version_local()
        return False, local, None


# ==================== ESTADO DE ACTUALIZACION ====================
def leer_estado():
    """Lee el archivo de estado del updater."""
    if not os.path.exists(ARCHIVO_ESTADO):
        return None
    try:
        with open(ARCHIVO_ESTADO, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Si el estado tiene mas de 10 minutos, considerarlo obsoleto
        fecha = datetime.fromisoformat(data.get('fecha', '2000-01-01T00:00:00'))
        if datetime.now() - fecha > timedelta(minutes=10):
            return None

        return data
    except Exception:
        return None


def escribir_estado(estado):
    """Escribe el estado del updater."""
    try:
        with open(ARCHIVO_ESTADO, 'w', encoding='utf-8') as f:
            json.dump(estado, f)
    except Exception:
        pass


def limpiar_estado():
    """Elimina el archivo de estado."""
    try:
        if os.path.exists(ARCHIVO_ESTADO):
            os.remove(ARCHIVO_ESTADO)
    except Exception:
        pass


# ==================== LANZAR ACTUALIZACION ====================
def lanzar_actualizacion():
    """
    Lanza el script de actualizacion usando el Task Scheduler de Windows
    (schtasks). Esto es critico porque NSSM mata el 'process tree' cuando
    se detiene el servicio Flask. Si usaramos Popen normal, el script moriria
    junto con Flask y nunca llegaria a reiniciar el servicio.

    Al usar schtasks, el script corre como proceso independiente del
    Service Control Manager, por lo que NSSM no puede matarlo.

    Retorna (exito, mensaje).
    """
    # Verificar que no haya una actualizacion en curso
    estado = leer_estado()
    if estado and estado.get('estado') == 'en_progreso':
        return False, 'Ya hay una actualizacion en curso.'

    # Ruta del script
    script = os.path.join(RAIZ, 'scripts', 'actualizar_sistema.py')
    if not os.path.exists(script):
        return False, f'No se encuentra el script: {script}'

    # Escribir estado inicial
    escribir_estado({
        'estado': 'en_progreso',
        'fecha': datetime.now().isoformat(),
        'paso': 'Iniciando...',
        'progreso': 0,
    })

    try:
        python_exe = sys.executable  # Python del venv (con todos los modulos)

        # Eliminar tarea previa si existe (por si quedo huerfana)
        try:
            subprocess.run(
                ['schtasks', '/Delete', '/TN', NOMBRE_TAREA, '/F'],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass

        # Hora de ejecucion: 1 minuto en el futuro (evita race conditions)
        hora_ejecucion = (datetime.now() + timedelta(minutes=1)).strftime('%H:%M')

        # Crear la tarea programada
        cmd_create = [
            'schtasks', '/Create', '/F',
            '/TN', NOMBRE_TAREA,
            '/TR', f'"{python_exe}" "{script}"',
            '/SC', 'ONCE',
            '/ST', hora_ejecucion,
            '/RL', 'HIGHEST',
            '/RU', 'SYSTEM',
        ]
        r = subprocess.run(cmd_create, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            limpiar_estado()
            err = (r.stderr or r.stdout or 'desconocido').strip()
            return False, f'Error creando tarea: {err[:200]}'

        # Ejecutar la tarea ya (no esperar a la hora programada)
        cmd_run = ['schtasks', '/Run', '/TN', NOMBRE_TAREA]
        r = subprocess.run(cmd_run, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            limpiar_estado()
            err = (r.stderr or r.stdout or 'desconocido').strip()
            return False, f'Error ejecutando tarea: {err[:200]}'

        return True, 'Actualizacion iniciada. El servicio se reiniciara en ~30 segundos.'

    except Exception as e:
        limpiar_estado()
        return False, f'Error al lanzar: {e}'