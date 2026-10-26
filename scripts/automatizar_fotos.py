import os
import sys
import subprocess
from PIL import Image

# 1. Configuración de carpetas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR) # <--- ESTA LÍNEA ARREGLA EL ERROR

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

ORIGEN = os.path.join(BASE_DIR, 'data', 'imagenes')
DESTINO = os.path.join(BASE_DIR, 'app', 'static', 'img', 'productos')

app = create_app()

def procesar_todo():
    print("--- INICIANDO AUTOMATIZACION DE FOTOS ---")
    
    with app.app_context():
        # A. Procesar imagenes fisicas
        for archivo in os.listdir(ORIGEN):
            if archivo.lower().endswith(('.jpg', '.jpeg', '.png')):
                codigo = os.path.splitext(archivo)[0]
                
                # Buscar si el producto existe en la DB
                prod = Producto.query.filter_by(codigo_barras=codigo).first()
                if prod:
                    ruta_origen = os.path.join(ORIGEN, archivo)
                    ruta_destino = os.path.join(DESTINO, f"{codigo}.webp")
                    
                    # Achicar y guardar como webp
                    img = Image.open(ruta_origen).convert("RGB")
                    img.thumbnail((150, 150))
                    img.save(ruta_destino, "WEBP", quality=80)
                    
                    # Actualizar DB Central
                    prod.imagen = f"{codigo}.webp"
                    db.session.commit()
                    
                    # Avisar a las tiendas que hay cambio
                    ProductoTienda.query.filter_by(producto_id=prod.id).update({'sync_estado': 'pendiente'})
                    db.session.commit()
                    print(f"OK: Foto procesada para {prod.nombre}")

    # B. Subir a GitHub automaticamente
    print("--- SUBIENDO A GITHUB ---")
    subprocess.run(["git", "add", "app/static/img/productos/"], check=True)
    # Solo hace commit si hay cambios reales
    status = subprocess.run(["git", "status", "--porcelain", "app/static/img/productos/"], capture_output=True, text=True)
    if status.stdout.strip():
        subprocess.run(["git", "commit", "-m", "feat: actualizacion automatica de fotos"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("--- GITHUB ACTUALIZADO ---")
    else:
        print("--- NO HABIA FOTOS NUEVAS PARA SUBIR ---")
        
    print("--- PROCESO TERMINADO. ESPERA 2 MINUTOS A QUE LAS TIENDAS SE ACTUALICEN ---")

if __name__ == '__main__':
    procesar_todo()