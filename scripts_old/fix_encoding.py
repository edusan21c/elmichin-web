# scripts/fix_encoding.py
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.extensions import db
from app.models.producto import Producto

def main():
    app = create_app()
    with app.app_context():
        productos = Producto.query.all()
        cambios = 0

        # Diccionario con los caracteres rotos exactos que vimos en la consola
        reemplazos = {
            'Âą': 'ñ',
            'Âž': 'ó',
            'Ăł': 'ó',
            'Ă': 'á',
            'Ă': 'í',
            'Âş': 'ú',
            'Â°': '°',
            'Â´': "'",
            'Â¨': 'ü',
            'Â¤': 'ñ',
            'Ăº': 'ú',
            'Ăł': 'ó'
        }

        for p in productos:
            if not p.nombre:
                continue
            
            nombre_original = p.nombre
            nombre_nuevo = nombre_original
            
            for roto, bueno in reemplazos.items():
                nombre_nuevo = nombre_nuevo.replace(roto, bueno)

            if nombre_nuevo != nombre_original:
                p.nombre = nombre_nuevo
                cambios += 1

        db.session.commit()
        print(f"--- SE CORRIGIERON {cambios} NOMBRES ---")

if __name__ == '__main__':
    main()