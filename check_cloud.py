from app import create_app
import requests

app = create_app()
with app.app_context():
    sync_key = app.config.get('SYNC_KEY', '')
    headers = {'X-Sync-Key': sync_key, 'X-Sync-Ack': 'true'}
    # Hacemos la misma petición que hace la Tienda 1
    r = requests.get('https://central.elmichin.com/api/sync/pull', params={'tienda_id': 1, 'desde': '2026-01-01T00:00:00', 'desde_id': 0}, headers=headers)
    print(f"Status: {r.status_code}")
    datos = r.json()
    print(f"Productos pendientes en la nube para T1: {len(datos.get('productos', []))}")
    if datos.get('productos'):
        print("Primeros productos:", [p['nombre'] for p in datos['productos'][:3]])
