from app import create_app
from app.extensions import db
from sqlalchemy import text, inspect
import os

app = create_app()
with app.app_context():
    print("=" * 60)
    print("DIAGNOSTICO DEL SISTEMA - EL MICHIN")
    print("=" * 60)
    
    # 1. Versión del código actual (esta PC)
    print("\n1. VERSION DE CODIGO EN ESTA PC:")
    try:
        with open(os.path.join('app', '__init__.py'), 'r', encoding='utf-8') as f:
            contenido = f.read()
            if 'v10' in contenido.lower() or 'anulacion' in contenido.lower():
                print("   ✅ Tiene codigo v10.x (con anulaciones)")
            else:
                print("   ⚠️ Revisar manualmente (no se detecto version)")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 2. Verificar columna anulada en esta BD
    print("\n2. COLUMNA 'anulada' EN ESTA BD:")
    try:
        insp = inspect(db.engine)
        cols = [c['name'] for c in insp.get_columns('facturas')]
        if 'anulada' in cols:
            print("   ✅ Columna 'anulada' existe")
        else:
            print("   ❌ FALTA columna 'anulada' - correr add_anulada.py")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 3. Facturas pendientes de sincronizar
    print("\n3. FACTURAS PENDIENTES DE SINCRONIZAR:")
    try:
        from app.models.factura import Factura
        pendientes = Factura.query.filter_by(sync_estado='pendiente').all()
        print(f"   📊 {len(pendientes)} facturas pendientes de enviar a la nube")
        for f in pendientes[:5]:
            print(f"      - {f.numero_factura} | Anulada: {getattr(f, 'anulada', 'N/A')} | Sync: {f.sync_estado}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 4. Verificar configuración de la nube
    print("\n4. CONFIGURACION DE NUBE:")
    print(f"   CENTRAL_URL: {app.config.get('CENTRAL_URL', 'NO CONFIGURADA')}")
    print(f"   SYNC_KEY: {'✅ Configurada' if app.config.get('SYNC_KEY') else '❌ NO CONFIGURADA'}")
    print(f"   TIENDA_ID: {app.config.get('TIENDA_ID', 'NO CONFIGURADA')}")
    
    # 5. Contar facturas anuladas
    print("\n5. FACTURAS ANULADAS EN ESTA BD:")
    try:
        from app.models.factura import Factura
        anuladas = Factura.query.filter_by(anulada=True).count()
        total = Factura.query.count()
        print(f"   🔴 {anuladas} anuladas de {total} totales")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 6. Últimos logs de sync
    print("\n6. ULTIMOS LOGS DE SINCRONIZACION (sync.log):")
    try:
        log_path = os.path.join('logs', 'sync.log')
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                lineas = f.readlines()[-10:]
            for l in lineas:
                print(f"   {l.strip()}")
        else:
            print("   ⚠️ No existe sync.log todavía")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 60)