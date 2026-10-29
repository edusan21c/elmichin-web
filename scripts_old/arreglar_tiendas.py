import re
import os

archivos = [
    r'app\blueprints\inventario\routes.py',
    r'app\blueprints\facturacion\routes.py',
    r'app\blueprints\reportes\routes.py'
]

nueva_funcion = '''def tienda_actual():
    from flask import session, current_app
    from app.models.tienda import Tienda

    if current_app.config.get('MODO') == 'central' and (current_user.es_programador() or current_user.es_admin()):
        tid = request.args.get('tienda', type=int)
        if tid:
            session['tienda_actual_id'] = tid
            return tid
        if session.get('tienda_actual_id'):
            return session.get('tienda_actual_id')
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None

    if current_user.tienda_id:
        return current_user.tienda_id

    return current_app.config.get('TIENDA_ID')'''

for archivo in archivos:
    if not os.path.exists(archivo):
        print(f"No existe: {archivo}")
        continue
        
    with open(archivo, 'r', encoding='utf-8') as f:
        contenido = f.read()
    
    # Busca la función tienda_actual y la reemplaza
    patron = r"def tienda_actual\(\):.*?(?=def |@bp\.route|$)"
    
    if re.search(patron, contenido, flags=re.DOTALL):
        nuevo_contenido = re.sub(patron, nueva_funcion + "\n\n\n", contenido, flags=re.DOTALL)
        with open(archivo, 'w', encoding='utf-8') as f:
            f.write(nuevo_contenido)
        print(f"OK: Arreglado exitosamente {archivo}")
    else:
        print(f"ATENCION: No se encontro la funcion en {archivo}")

print("\n--- PROCESO TERMINADO ---")