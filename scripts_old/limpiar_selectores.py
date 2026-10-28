# scripts/limpiar_selectores.py
import os
import re

# Ruta a la carpeta de templates
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'templates')

archivos_modificados = 0

for root, dirs, files in os.walk(TEMPLATES_DIR):
    for file in files:
        if file.endswith('.html'):
            ruta = os.path.join(root, file)
            with open(ruta, 'r', encoding='utf-8') as f:
                contenido = f.read()

            # Si el archivo tiene el selector local viejo
            if 'id="selector-tienda"' in contenido:
                # Reemplazar el bloque {% if ... %} ... {% endif %} que lo contiene
                # Esto busca desde "{% if current_user.es_programador()" hasta el "{% endif %}" más cercano
                patron = re.compile(r'\{%\s*if\s+current_user\.es_programador\(\).*?\%\}.*?id="selector-tienda".*?\{%.*?endif\s*%\}', re.DOTALL)
                nuevo_contenido = patron.sub('', contenido)
                
                # Si quedaron textos sueltos como "- Tienda:" o "- Viendo:", los limpiamos
                nuevo_contenido = nuevo_contenido.replace('- Tienda:', '').replace('- Viendo:', '')

                # Guardar si hubo cambios
                if nuevo_contenido != contenido:
                    with open(ruta, 'w', encoding='utf-8') as f:
                        f.write(nuevo_contenido)
                    print(f"[OK] Limpiado: {ruta}")
                    archivos_modificados += 1

print(f"\n--- SE LIMPIARON {archivos_modificados} ARCHIVOS HTML ---")