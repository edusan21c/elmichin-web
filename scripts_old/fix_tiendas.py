# scripts/fix_tiendas.py
import os

# Ruta base de los blueprints
BLUEPRINTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'blueprints')

# La nueva función que queremos inyectar (segura, sin depender de es_central)
NUEVA_FUNCION = """def tienda_actual():
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
    return current_user.tienda_id
"""

archivos_modificados = 0

for root, dirs, files in os.walk(BLUEPRINTS_DIR):
    for file in files:
        if file.endswith('.py'):
            ruta_archivo = os.path.join(root, file)
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                lineas = f.readlines()
            
            encontrado = False
            nuevas_lineas = []
            i = 0
            while i < len(lineas):
                if lineas[i].startswith('def tienda_actual():'):
                    encontrado = True
                    # Saltar hasta el final de la función
                    i += 1
                    while i < len(lineas):
                        linea = lineas[i]
                        # La función termina cuando hay una línea vacía o una línea que no tiene indentación
                        if linea.strip() == '' or (not linea.startswith(' ') and not linea.startswith('\t')):
                            break
                        i += 1
                    # Reemplazar con la nueva función
                    nuevas_lineas.append(NUEVA_FUNCION + '\n')
                    # Si la línea siguiente es vacía, añadirla para mantener el formato
                    if i < len(lineas) and lineas[i].strip() == '':
                        nuevas_lineas.append('\n')
                        i += 1
                    continue
                else:
                    nuevas_lineas.append(lineas[i])
                    i += 1
            
            if encontrado:
                with open(ruta_archivo, 'w', encoding='utf-8') as f:
                    f.writelines(nuevas_lineas)
                print(f'[OK] Modificado: {ruta_archivo}')
                archivos_modificados += 1

print(f'\n--- SE MODIFICARON {archivos_modificados} ARCHIVOS ---')