from app import create_app
from app.services import sync_service
import requests

app = create_app()
with app.app_context():
    pendientes = sync_service.obtener_pendientes_push(0)
    pendientes['productos'] = sync_service.obtener_productos_pendientes_push(0)
    
    productos_t1 = [p for p in pendientes['productos'] if p['tienda_id'] == 1]
    productos_t2 = [p for p in pendientes['productos'] if p['tienda_id'] == 2]
    
    print(f"Productos pendientes para Tienda 1: {len(productos_t1)}")
    print(f"Productos pendientes para Tienda 2: {len(productos_t2)}")
    
    central_url = app.config.get('CENTRAL_URL', 'https://central.elmichin.com').rstrip('/')
    sync_key = app.config.get('SYNC_KEY', '')
    
    for t_id, prods in [(1, productos_t1), (2, productos_t2)]:
        if prods:
            print(f"\nEnviando {len(prods)} productos a Tienda {t_id}...")
            payload = {
                'tienda_id': t_id,
                'productos': prods,
                'facturas': [], 'pagos': [], 'clientes': [], 'configuracion': []
            }
            r = requests.post(central_url + '/api/sync/push', json=payload, headers={'X-Sync-Key': sync_key}, timeout=10)
            print(f"Código HTTP: {r.status_code}")
            print(f"Respuesta: {r.text}")
            if r.status_code == 200 and r.json().get('ok'):
                sync_service.marcar_sincronizados(t_id, r.json())
                print(f"¡Productos de Tienda {t_id} marcados como sincronizados!")
