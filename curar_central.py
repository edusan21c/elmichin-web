import requests
from app import create_app
from app.services import sync_service

app = create_app()
with app.app_context():
    central_url = app.config.get('CENTRAL_URL', '').rstrip('/')
    sync_key = app.config.get('SYNC_KEY', '')
    headers = {'X-Sync-Key': sync_key, 'X-Sync-Ack': 'true'}
    
    print("Forzando a la Central a descargar el catálogo de la Tienda 1...")
    # Pedimos los productos de la Tienda 1 (tienda_id=1) desde el principio
    r = requests.get(central_url + '/api/sync/pull', params={'tienda_id': 1, 'desde_id': 0}, headers=headers)
    
    if r.status_code == 200:
        datos = r.json()
        prods = datos.get('productos', [])
        print(f"Productos recibidos de la Tienda 1: {len(prods)}")
        if prods:
            res = sync_service.aplicar_cambios_pull({'productos': prods})
            print(f"Resultado: {res['actualizados']} actualizados, {res['creados']} creados.")
    else:
        print(f"Error HTTP {r.status_code}: {r.text}")
