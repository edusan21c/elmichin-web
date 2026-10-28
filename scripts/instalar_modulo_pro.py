import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT_PATH = os.path.join(BASE_DIR, 'app', '__init__.py')

def instalar():
    if not os.path.exists(INIT_PATH):
        print("ERROR: No se encontró app/__init__.py")
        return

    with open(INIT_PATH, 'r', encoding='utf-8') as f:
        contenido = f.read()

    if 'inventario_pro' in contenido:
        print("El módulo PRO ya estaba registrado.")
        return

    # Buscamos donde se registra el blueprint del dashboard
    patron = r"(from app\.blueprints\.dashboard import bp as dashboard_bp\napp\.register_blueprint\(dashboard_bp.*?\))"
    
    match = re.search(patron, contenido)
    if match:
        texto_original = match.group(1)
        texto_nuevo = texto_original + "\n\nfrom app.blueprints.inventario_pro import bp as inventario_pro_bp\napp.register_blueprint(inventario_pro_bp, url_prefix='/inventario-pro')"
        
        nuevo_contenido = contenido.replace(texto_original, texto_nuevo)
        
        with open(INIT_PATH, 'w', encoding='utf-8') as f:
            f.write(nuevo_contenido)
            
        print("¡Módulo PRO registrado exitosamente en app/__init__.py!")
    else:
        print("No se encontró el registro del dashboard. Pásame una captura de tu archivo app/__init__.py")

if __name__ == '__main__':
    instalar()