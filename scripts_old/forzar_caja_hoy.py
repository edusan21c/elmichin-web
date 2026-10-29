import os
import re

archivo = r'C:\michin_web\app\blueprints\caja\routes.py'

with open(archivo, 'r', encoding='utf-8') as f:
    contenido = f.read()

# 1. Modificamos el parámetro 'periodo' por defecto para que sea 'dia' (Hoy)
# Buscamos si el sistema lee un parámetro de periodo
if "request.args.get('periodo'" in contenido:
    contenido = re.sub(r"request\.args\.get\('periodo',\s*'[^']*'\)", "request.args.get('periodo', 'dia')", contenido)

# 2. Buscamos cómo se calculan las fechas (desde y hasta) si no vienen por la URL
# Normalmente el sistema pone la fecha de inicio del mes. Lo forzamos a hoy.
patron_fecha_desde = r"if not desde_str:\s*(.*?)\n"
reemplazo_fecha_desde = "if not desde_str:\n        desde_str = hoy.strftime('%Y-%m-%d')\n"
contenido = re.sub(patron_fecha_desde, reemplazo_fecha_desde, contenido)

with open(archivo, 'w', encoding='utf-8') as f:
    f.write(contenido)

print("OK: La Caja ahora abrirá siempre por defecto en la vista de HOY (Día).")