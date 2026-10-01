# run_prod.py
# Servidor de produccion con Waitress para El Michin.
# Ejecutar: python run_prod.py
# O como servicio de Windows (ver scripts\instalar_servicio_flask.ps1)

import os
import sys
from datetime import datetime

# Zona horaria Colombia
os.environ['TZ'] = 'America/Bogota'

from waitress import serve
from app import create_app

app = create_app()


def log(msg):
    """Log simple con timestamp."""
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ahora}] {msg}', flush=True)


if __name__ == '__main__':
    log('=' * 60)
    log('EL MICHIN - Servidor de Produccion (Waitress)')
    log('=' * 60)
    log(f'Modo: {app.config["MODO"]}')
    log(f'Tienda ID: {app.config["TIENDA_ID"]}')
    log(f'DB: {app.config["DB_NAME"]}')
    log('URL local: http://localhost:5000')
    log('URL publica: https://central.elmichin.com')
    log('=' * 60)
    log('Servidor iniciado. Presiona Ctrl+C para detener.')
    log('')

    try:
        serve(
            app,
            host='0.0.0.0',
            port=5000,
            threads=8,
            connection_limit=100,
            channel_timeout=300,
            cleanup_interval=30,
            url_scheme='https',
        )
    except KeyboardInterrupt:
        log('Servidor detenido por el usuario.')
        sys.exit(0)
    except Exception as e:
        log(f'ERROR FATAL: {e}')
        sys.exit(1)
