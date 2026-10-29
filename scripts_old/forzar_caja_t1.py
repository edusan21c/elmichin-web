import os
import re

archivo = r'C:\michin_web\app\blueprints\caja\routes.py'

with open(archivo, 'r', encoding='utf-8') as f:
    contenido = f.read()

# Volvemos a poner la función tienda_actual original, que por defecto muestra T1
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

# Reemplazamos la función actual
patron = r"def tienda_actual\(\):.*?(?=def |@bp\.route|$)"
contenido = re.sub(patron, nueva_funcion + "\n\n\n", contenido, flags=re.DOTALL)

# Nos aseguramos de que el filtro de INACTIVO se aplique siempre
contenido = contenido.replace(
    "if tienda_id:\n            q = q.filter((Factura.tienda_id == tienda_id if tienda_id else True), Producto.categoria != 'INACTIVO')",
    "if tienda_id:\n            q = q.filter(Factura.tienda_id == tienda_id)\n        q = q.filter(Producto.categoria != 'INACTIVO')"
)

with open(archivo, 'w', encoding='utf-8') as f:
    f.write(contenido)

print("OK: La Caja en la Central ahora mostrará T1 por defecto (No la suma global).")