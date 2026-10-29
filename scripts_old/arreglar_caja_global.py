import os
import re

archivo = r'C:\michin_web\app\blueprints\caja\routes.py'

with open(archivo, 'r', encoding='utf-8') as f:
    contenido = f.read()

# 1. Modificamos tienda_actual para que devuelva None (Global) si no se elige tienda
nueva_funcion = '''def tienda_actual():
    from flask import session, current_app
    from app.models.tienda import Tienda

    if current_app.config.get('MODO') == 'central' and (current_user.es_programador() or current_user.es_admin()):
        tid = request.args.get('tienda', type=int)
        if tid:
            session['tienda_actual_id'] = tid
            return tid
        # Si no elige tienda, devolvemos None para sumar TODAS
        return None

    if current_user.tienda_id:
        return current_user.tienda_id

    return current_app.config.get('TIENDA_ID')'''

# Reemplazamos la función vieja
patron = r"def tienda_actual\(\):.*?(?=def |@bp\.route|$)"
contenido = re.sub(patron, nueva_funcion + "\n\n\n", contenido, flags=re.DOTALL)

# 2. Hacemos que las consultas SQL sumen todo si tienda_id es None
contenido = contenido.replace(
    "Factura.tienda_id == tienda_id", 
    "(Factura.tienda_id == tienda_id if tienda_id else True)"
)

with open(archivo, 'w', encoding='utf-8') as f:
    f.write(contenido)

print("OK: La Caja ahora mostrará el TOTAL GLOBAL si no se selecciona una tienda.")