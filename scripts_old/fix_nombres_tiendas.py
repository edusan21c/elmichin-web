# scripts/fix_nombres_tiendas.py
import sys
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.extensions import db
from app.models.tienda import Tienda


def main():
    app = create_app()
    with app.app_context():
        t1 = Tienda.query.get(1)
        t2 = Tienda.query.get(2)

        if t1:
            t1.nombre = 'El Michín Uno'
            print(f'Tienda 1: {t1.nombre}')
        if t2:
            t2.nombre = 'El Michín Dos'
            print(f'Tienda 2: {t2.nombre}')

        db.session.commit()
        print('Nombres actualizados correctamente.')


if __name__ == '__main__':
    main()