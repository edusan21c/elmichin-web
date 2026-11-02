from app import create_app
from app.extensions import db
from app.services import sync_service
import requests
import json

app = create_app()
with app.app_context():
    print("=" * 60)
    print("TEST DE PUSH REAL A LA NUBE")
    print("=" * 60)
    
    tienda_id = 1
    central_url = app.config.get('CENTRAL_URL', '').rstrip('/')
    sync_key = app.config.get('SYNC_KEY', '')
    
    print(f"\n1. URL NUBE: {central_url}")
    print(f"2. SYNC_KEY: {sync_key[:8]}..." if sync_key else "2. SYNC_KEY: ❌ VACIA")
    
    # ¿La nube responde?
    print("\n3. PROBANDO PING A LA NUBE...")
    try:
        r = requests.get(central_url + '/api/sync/ping', timeout=10)
        print(f"   Status: {r.status_code}")
        print(f"   Respuesta: {r.text[:200]}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        exit()
    
    # Preparar el paquete de facturas pendientes
    print("\n4. PREPARANDO PUSH DE FACTURAS PENDIENTES...")
    pendientes = sync_service.obtener_pendientes_push(tienda_id)
    print(f"   Facturas a enviar: {len(pendientes['facturas'])}")
    print(f"   Clientes a enviar: {len(pendientes['clientes'])}")
    print(f"   Pagos a enviar: {len(pendientes['pagos'])}")
    
    if len(pendientes['facturas']) == 0:
        print("   ⚠️ No hay facturas pendientes. Nada que enviar.")
        exit()
    
    # Ver qué contiene el payload de la factura
    print("\n5. CONTENIDO DE LA PRIMERA FACTURA:")
    factura_data = pendientes['facturas'][0]
    print(f"   {json.dumps(factura_data, indent=2, default=str)[:800]}")
    
    # Enviar a la nube
    print("\n6. ENVIANDO A LA NUBE (PUSH MANUAL)...")
    try:
        r = requests.post(
            central_url + '/api/sync/push',
            json={'tienda_id': tienda_id, **pendientes},
            headers={'X-Sync-Key': sync_key},
            timeout=30
        )
        print(f"   Status HTTP: {r.status_code}")
        print(f"   Respuesta Nube: {r.text[:500]}")
        
        if r.status_code == 200 and r.json().get('ok'):
            print("\n   ✅ LA NUBE ACEPTÓ EL PUSH")
            sync_service.marcar_sincronizados(tienda_id, r.json())
            print("   ✅ Marcadas como sincronizadas localmente")
        else:
            print(f"\n   ❌ LA NUBE RECHAZÓ EL PUSH")
            print(f"   Esto significa que la nube NO tiene el código v10.1 actualizado")
    except Exception as e:
        print(f"   ❌ ERROR DE RED: {e}")
    
    print("\n" + "=" * 60)