import os
import re
import shutil

# 1. Borrar la caché de Python
for root, dirs, files in os.walk(r'C:\michin_web\app'):
    for d in dirs:
        if d == '__pycache__':
            shutil.rmtree(os.path.join(root, d), ignore_errors=True)
print("OK: Caché de Python eliminada.")

archivo = r'C:\michin_web\app\blueprints\caja\routes.py'

with open(archivo, 'r', encoding='utf-8') as f:
    contenido = f.read()

# 2. Inyectar el salto en el bucle del gráfico
# Buscamos la línea exacta que arma la categoría
patron = r"(cat = \(prod\.categoria if prod and prod\.categoria else 'Sin categoría'\)\.strip\(\))"
reemplazo = r"\1\n            if cat == 'INACTIVO':\n                continue"

if "if cat == 'INACTIVO':" not in contenido:
    nuevo_contenido = re.sub(patron, reemplazo, contenido)
    
    if nuevo_contenido != contenido:
        with open(archivo, 'w', encoding='utf-8') as f:
            f.write(nuevo_contenido)
        print("OK: Se agregó el filtro de Python para ignorar INACTIVO en el gráfico.")
    else:
        print("ATENCION: No se encontró el patrón exacto.")
else:
    print("OK: El filtro de Python ya estaba puesto.")