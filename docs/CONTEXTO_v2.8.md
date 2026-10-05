# CONTEXTO v2.8 - Sync bidireccional de productos

## Estoy implementando
Sync bidireccional de precios y stock POR TIENDA (T1 y T2 independientes).

## Estado actual
- ✅ sync_service.py — CORREGIDO (ya tiene productos_ok, aplicar stock en pull)
- ✅ api/sync.py — CORREGIDO (sync_pull recibe tienda_id)
- ⚠️ inventario/routes.py — FALTA 1 línea en actualizar_stock()
- 🚨 scripts/sync_worker.py — ESTÁ ROTO, necesita reemplazo

## Archivos que FALTAN corregir

### inventario/routes.py — en actualizar_stock()
Buscá:
    cantidad_vieja = pres.cantidad
    pres.cantidad = cantidad
    db.session.commit()

Reemplazar por:
    cantidad_vieja = pres.cantidad
    pres.cantidad = cantidad
    pres.sync_estado = 'pendiente'
    pres.sync_fecha = datetime.utcnow()
    db.session.commit()

### scripts/sync_worker.py — REEMPLAZAR COMPLETO
(el archivo está roto: hacer_push corrupto, hacer_pull sin tienda_id)

## Comandos para verificar
C:\michin_web\venv\Scripts\python.exe -c "import ast; ast.parse(open(r'C:\michin_web\app\services\sync_service.py', encoding='utf-8').read()); print('service OK')"
C:\michin_web\venv\Scripts\python.exe -c "import ast; ast.parse(open(r'C:\michin_web\app\blueprints\api\sync.py', encoding='utf-8').read()); print('api OK')"
C:\michin_web\venv\Scripts\python.exe -c "import ast; ast.parse(open(r'C:\michin_web\app\blueprints\inventario\routes.py', encoding='utf-8').read()); print('inventario OK')"
C:\michin_web\venv\Scripts\python.exe -c "import ast; ast.parse(open(r'C:\michin_web\scripts\sync_worker.py', encoding='utf-8').read()); print('worker OK')"

## Commit + push + tag
cd C:\michin_web
git add .
git commit -m "feat(sync): sync bidireccional de precios y stock por tienda"
git push origin main
git tag -a v2.8 -m "v2.8: Sync de productos (precios + stock)"
git push origin v2.8

## Después de pushear
1. Ir a central → probar que funciona el sync
2. Ir a Tienda 1 → apretar botón "Actualizar" → debe bajar v2.8
3. En central → editar precio de producto T1 → verificar que baja a T1
4. En T1 → editar stock → verificar que sube a central
5. Verificar que T2 NO se afecta

## Credenciales
- PostgreSQL: Michin2026!Seguro
- SYNC_KEY: vKtm_E5Pfh1Xgo64B-fhB8fcf3xNhYaJOlGYxVhhLrlFN--sGmDqyg
- programador / eduar1985

## Repo
https://github.com/edusan21c/elmichin-web