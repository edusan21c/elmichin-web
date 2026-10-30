import sys
import os
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from app.models.producto import Producto

app = create_app()
with app.app_context():
    codigos = ['7622201776565', 'b4fe3aa9ab0b', '7702133452413', '2004394818317', 'd45b8acf285b', 'cfddbf52e473']
    img_dir = r'C:\michin_web\app\static\img\productos'
    
    print('--- REVISANDO FOTOS DE TRIDENT EN LA CENTRAL ---')
    for c in codigos:
        p = Producto.query.filter_by(codigo_barras=c).first()
        if p:
            tiene_foto_db = p.imagen if p.imagen else "NO"
            ruta_fisica = os.path.join(img_dir, p.imagen) if p.imagen else None
            existe_fisico = os.path.exists(ruta_fisica) if ruta_fisica else False
            
            print(f'Producto: {p.nombre}')
            print(f'  - Nombre en BD: {tiene_foto_db}')
            print(f'  - Archivo físico: {"EXISTE" if existe_fisico else "NO EXISTE"}')
        else:
            print(f'Código {c} NO encontrado en la Central.')
        print('-' * 40)
