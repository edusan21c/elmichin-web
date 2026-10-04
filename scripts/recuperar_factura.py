# scripts/recuperar_factura.py
# Recupera UNA factura específica del central y la inserta en la tienda local.
# Uso: python scripts\recuperar_factura.py REM-T1-0001
import os
import sys
import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.services import sync_service


def leer_env():
    config = {}
    with open(os.path.join(RAIZ, '.env'), 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()
    return config


def main():
    if len(sys.argv) < 2:
        print('Uso: python scripts\\recuperar_factura.py REM-T1-0001')
        return

    numero = sys.argv[1]
    cfg = leer_env()
    app = create_app()

    with app.app_context():
        tienda_id = app.config.get('TIENDA_ID', 1)
        central = app.config.get('CENTRAL_URL', '').rstrip('/')
        key = app.config.get('SYNC_KEY', '')

        print(f'Pidiendo {numero} al central ({central})...')

        try:
            r = requests.get(
                f'{central}/api/sync/factura/{numero}',
                params={'tienda_id': tienda_id},
                headers={'X-Sync-Key': key},
                timeout=30,
            )
        except requests.RequestException as e:
            print(f'ERROR de red: {e}')
            return

        if r.status_code != 200:
            print(f'ERROR: HTTP {r.status_code}')
            print(r.text[:500])
            return

        data = r.json()
        if not data.get('ok'):
            print(f'ERROR: {data.get("error")}')
            return

        resultado = sync_service.aplicar_facturas_recibidas(
            tienda_id, [data['factura']]
        )
        print(f'OK: {resultado} factura(s) insertadas')


if __name__ == '__main__':
    main()