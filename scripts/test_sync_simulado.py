# scripts/test_sync_simulado.py
# Simula el envio de datos de una tienda al central.
# Uso: python scripts\test_sync_simulado.py

import sys
import os
import json
from datetime import datetime

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def leer_env():
    env_path = os.path.join(RAIZ, '.env')
    config = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()
    return config


def main():
    cfg = leer_env()
    sync_key = cfg.get('SYNC_KEY', '')
    central_url = cfg.get('CENTRAL_URL', 'http://localhost:5000')

    if not sync_key:
        print('ERROR: SYNC_KEY no encontrada en .env')
        return

    # Payload simulado
    payload = {
        'tienda_id': 1,
        'facturas': [
            {
                'id': 9999,
                'numero_factura': 'FAC-T1-TEST01',
                'tienda_id': 1,
                'fecha_hora': datetime.utcnow().isoformat(),
                'cliente_id': 8888,
                'usuario_id': None,
                'subtotal': 5000,
                'total': 5000,
                'metodo_pago': 'efectivo',
                'recargo_nequi': 0,
                'recargo_bolsa': 0,
                'valor_pagado': 5000,
                'vueltas': 0,
                'tipo_pago': 'contado',
                'estado_credito': 'pagado',
                'saldo_pendiente': 0,
                'detalles': [
                    {
                        'producto_id': 1,
                        'producto_nombre': 'Producto de prueba',
                        'cantidad': 2,
                        'precio_unitario': 2500,
                        'subtotal': 5000,
                    }
                ],
            }
        ],
        'pagos': [],
        'clientes': [
            {
                'id': 8888,
                'tienda_id': 1,
                'nombre': 'Cliente Test Sincronizado',
                'documento': '123456789',
                'direccion': 'Calle Test',
                'telefono': '3001234567',
                'email': '',
                'saldo_actual': 0,
            }
        ],
    }

    print('=' * 60)
    print('TEST DE SINCRONIZACION SIMULADA')
    print('=' * 60)
    print()
    print(f'Enviando a: {central_url}/api/sync/push')
    print(f'Tienda: {payload["tienda_id"]}')
    print(f'Facturas: {len(payload["facturas"])}')
    print(f'Clientes: {len(payload["clientes"])}')
    print()

    try:
        r = requests.post(
            central_url.rstrip('/') + '/api/sync/push',
            json=payload,
            headers={'X-Sync-Key': sync_key},
            timeout=30,
        )
        print(f'HTTP {r.status_code}')
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except requests.RequestException as e:
        print(f'ERROR de red: {e}')


if __name__ == '__main__':
    main()