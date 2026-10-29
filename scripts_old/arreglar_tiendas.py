import os
import re

base_dir = r'C:\michin_web\app\blueprints'

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

arreglados = 0

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file == 'routes.py':
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'def tienda_actual():' in content:
                patron = r"def tienda_actual\(\):.*?(?=def |@bp\.route|$)"
                if re.search(patron, content, flags=re.DOTALL):
                    nuevo_contenido = re.sub(patron, nueva_funcion + "\n\n\n", content, flags=re.DOTALL)
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(nuevo_contenido)
                    print(f"OK: Arreglado -> {path}")
                    arreglados += 1

print(f"\n--- TERMINADO. Se arreglaron {arreglados} archivos. ---")