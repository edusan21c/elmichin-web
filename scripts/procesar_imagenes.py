# scripts/procesar_imagenes.py
import os
import sys
from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.extensions import db
from app.models.producto import Producto

CARPETA_ORIGEN = os.path.join(RAIZ, 'data', 'imagenes')
CARPETA_DESTINO = os.path.join(RAIZ, 'app', 'static', 'img', 'productos')

def procesar_imagenes():
    app = create_app()
    with app.app_context():
        # Crear carpeta destino si no existe
        if not os.path.exists(CARPETA_DESTINO):
            os.makedirs(CARPETA_DESTINO)
            
        if not os.path.exists(CARPETA_ORIGEN):
            print(f"ERROR: No existe la carpeta {CARPETA_ORIGEN}. Créala y pon las fotos ahí.")
            return

        actualizados = 0
        no_encontrados = 0

        for archivo in os.listdir(CARPETA_ORIGEN):
            if archivo.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                # El nombre del archivo sin extensión es el código de barras
                codigo_barras = os.path.splitext(archivo)[0]
                
                # Buscar el producto en la DB
                prod = Producto.query.filter_by(codigo_barras=codigo_barras).first()
                if prod:
                    try:
                        # Abrir y redimensionar a 150x150 cuadrados
                        img = Image.open(os.path.join(CARPETA_ORIGEN, archivo))
                        img = img.convert('RGB')
                        
                        # Hacer la imagen cuadrada
                        min_dim = min(img.size)
                        left = (img.size[0] - min_dim) / 2
                        top = (img.size[1] - min_dim) / 2
                        right = (img.size[0] + min_dim) / 2
                        bottom = (img.size[1] + min_dim) / 2
                        img = img.crop((left, top, right, bottom))
                        
                        img = img.resize((150, 150), Image.Resampling.LANCZOS)
                        
                        # Guardar como WebP (súper liviano)
                        nuevo_nombre = f"{codigo_barras}.webp"
                        ruta_destino = os.path.join(CARPETA_DESTINO, nuevo_nombre)
                        img.save(ruta_destino, 'WEBP', quality=80)
                        
                        # Actualizar DB
                        prod.imagen = nuevo_nombre
                        actualizados += 1
                        
                    except Exception as e:
                        print(f"Error procesando {archivo}: {e}")
                else:
                    no_encontrados += 1

        db.session.commit()
        print(f"--- IMAGENES PROCESADAS CON EXITO: {actualizados} ---")
        if no_encontrados > 0:
            print(f"--- OJO: {no_encontrados} fotos no coinciden con ningun codigo de barras en la DB ---")

if __name__ == '__main__':
    procesar_imagenes()