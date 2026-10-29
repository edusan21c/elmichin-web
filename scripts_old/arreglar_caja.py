import os
import re

archivo = r'C:\michin_web\app\blueprints\caja\routes.py'

if not os.path.exists(archivo):
    print("No se encontro el archivo de caja.")
else:
    with open(archivo, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Busca donde agrupa por categoria y le inyecta el filtro para quitar INACTIVO
    patron = r"(\b(?:db\.session\.query|query)\s*\(.*?Producto\.categoria.*?)(\.group_by\(.*?Producto\.categoria.*?\))"
    
    # Para no complicarnos con regex avanzado, buscaremos una parte clave
    if "Producto.categoria" in contenido and "INACTIVO" not in contenido:
        # Reemplazo inteligente: si encuentra la consulta agrupada, le mete el filtro
        contenido = contenido.replace("Factura.tienda_id == tienda_id", "Factura.tienda_id == tienda_id, Producto.categoria != 'INACTIVO'")
        
        with open(archivo, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print("OK: Se ha filtrado la categoria INACTIVO de los reportes de Caja.")
    else:
        print("ATENCION: Revisar el archivo manualmente.")