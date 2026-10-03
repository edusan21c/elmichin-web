# run_prod.py
# Servidor de produccion con Waitress para El Michin.
# Ejecutar: python run_prod.py
# O como servicio de Windows (ver scripts\instalar_servicio_flask.ps1)

import os
import sys
import threading
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


def servir(host, etiqueta):
    """Levanta un servidor Waitress. Se usa en un thread."""
    try:
        log(f'Iniciando servidor {etiqueta} en {host}:5000')
        serve(
            app,
            host=host,
            port=5000,
            threads=8,
            connection_limit=100,
            channel_timeout=300,
            cleanup_interval=30,
            # url_scheme='https',   # Comentado: Cloudflare Tunnel ya maneja HTTPS
        )
    except Exception as e:
        log(f'ERROR {etiqueta}: {e}')


if __name__ == '__main__':
    log('=' * 60)
    log('EL MICHIN - Servidor de Produccion (Waitress)')
    log('=' * 60)
    log(f'Modo: {app.config["MODO"]}')
    log(f'Tienda ID: {app.config["TIENDA_ID"]}')
    log(f'DB: {app.config["DB_NAME"]}')
    log('URL local:  http://localhost:5000')
    log('URL LAN:    http://192.168.0.x:5000')
    log('URL publica: https://central.elmichin.com')
    log('=' * 60)
    log('Servidor iniciado. Presiona Ctrl+C para detener.')
    log('')

    try:
        # Waitress en Windows no soporta dual-stack nativo.
        # Levantamos 2 instancias: una IPv4 y otra IPv6, en el mismo puerto.
        t_ipv4 = threading.Thread(
            target=servir, args=('0.0.0.0', 'IPv4'), daemon=True
        )
        t_ipv6 = threading.Thread(
            target=servir, args=('::', 'IPv6'), daemon=True
        )
        t_ipv4.start()
        t_ipv6.start()

        # Esperar a que ambas terminen (bloquea el proceso principal)
        t_ipv4.join()
        t_ipv6.join()

    except KeyboardInterrupt:
        log('Servidor detenido por el usuario.')
        sys.exit(0)
    except Exception as e:
        log(f'ERROR FATAL: {e}')
        sys.exit(1)