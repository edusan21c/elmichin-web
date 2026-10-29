import os
import shutil

BASE_DIR = r'C:\michin_web'
ORIGEN = os.path.join(BASE_DIR, 'data', 'imagenes')
PROCESADAS = os.path.join(BASE_DIR, 'data', 'imagenes_procesadas')
DESTINO = os.path.join(BASE_DIR, 'app', 'static', 'img', 'productos')

# Importamos la app para leer la base de datos
import sys
sys.path.append(BASE_DIR)
from app import create_app
from app.extensions import db
from app.models.producto import Producto

app = create_app()
with app.app_context():
    productos = Producto.query.all()
    arreglados = 0

    for p in productos:
        if not p.codigo_barras:
            continue
            
        codigo_actual = p.codigo_barras
        imagen_actual = p.imagen

        # Si tiene una foto asignada, pero el nombre no coincide con el código actual
        if imagen_actual:
            nombre_base = imagen_actual.split('.')[0]
            
            if nombre_base != codigo_actual:
                print(f"Corrigiendo {p.nombre}: {nombre_base} -> {codigo_actual}")
                
                # 1. Renombrar el archivo en static/img/productos
                for ext in ['.webp', '.jpg', '.jpeg', '.png']:
                    viejo = os.path.join(DESTINO, f"{nombre_base}{ext}")
                    nuevo = os.path.join(DESTINO, f"{codigo_actual}{ext}")
                    if os.path.exists(viejo):
                        if os.path.exists(nuevo):
                            os.remove(nuevo) # Si ya existía uno con el nuevo nombre, lo reemplazamos
                        os.rename(viejo, nuevo)

                # 2. Renombrar el archivo original en data/imagenes
                for ext in ['.jpeg', '.jpg', '.png', '.webp', '.JPG', '.JPEG', '.PNG']:
                    viejo = os.path.join(ORIGEN, f"{nombre_base}{ext}")
                    nuevo = os.path.join(ORIGEN, f"{codigo_actual}{ext}")
                    if os.path.exists(viejo):
                        if os.path.exists(nuevo): os.remove(nuevo)
                        os.rename(viejo, nuevo)
                        
                    viejo_proc = os.path.join(PROCESADAS, f"{nombre_base}{ext}")
                    nuevo_proc = os.path.join(PROCESADAS, f"{codigo_actual}{ext}")
                    if os.path.exists(viejo_proc):
                        if os.path.exists(nuevo_proc): os.remove(nuevo_proc)
                        os.rename(viejo_proc, nuevo_proc)

                # 3. Actualizar la base de datos
                p.imagen = f"{codigo_actual}.webp"
                arreglados += 1

    if arreglados > 0:
        db.session.commit()
        print(f"\n--- TERMINADO. Se corrigieron {arreglados} fotos. ---")
    else:
        print("\n--- TERMINADO. Todo estaba en orden. ---")