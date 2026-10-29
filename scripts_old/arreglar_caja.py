import os
import re

archivo = r'C:\michin_web\app\blueprints\caja\routes.py'

if not os.path.exists(archivo):
    print("No se encontro el archivo de caja.")
else:
    with open(archivo, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if "Producto.categoria != 'INACTIVO'" not in contenido:
        # Busca patrones comunes de filtro en SQLAlchemy y los reemplaza
        nuevo_contenido = re.sub(
            r"\.filter\(\s*Factura\.tienda_id\s*==\s*tienda_id\s*\)", 
            ".filter(Factura.tienda_id == tienda_id, Producto.categoria != 'INACTIVO')", 
            contenido
        )
        
        if nuevo_contenido == contenido:
             nuevo_contenido = re.sub(
                r"\.filter_by\(\s*tienda_id\s*=\s*tienda_id\s*\)", 
                ".filter(Factura.tienda_id == tienda_id, Producto.categoria != 'INACTIVO')", 
                contenido
            )

        if nuevo_contenido != contenido:
            with open(archivo, 'w', encoding='utf-8') as f:
                f.write(nuevo_contenido)
            print("OK: Se ha agregado el filtro de INACTIVO exitosamente en Caja.")
        else:
            print("ATENCION: No se encontro el patron exacto. Se requiere revision manual del archivo routes.py de caja.")
    else:
        print("OK: La Caja ya tenia el filtro de INACTIVO configurado.")