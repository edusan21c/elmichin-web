# scripts/crear_datos_iniciales.py
# Crea las 2 tiendas, el programador y usuarios de ejemplo.
# Ejecutar UNA VEZ después de las migraciones:
#   python scripts\crear_datos_iniciales.py

import sys
import os

# Asegurar que podemos importar 'app'
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.extensions import db
from app.models.tienda import Tienda
from app.models.usuario import Usuario
from app.utils.seguridad import hash_password


def crear_datos():
    app = create_app()
    with app.app_context():
        print('Creando datos iniciales...')
        print('-' * 60)

        # ---------- TIENDAS ----------
        tiendas_data = [
            {'id': 1, 'nombre': 'El Michín Lucero',  'direccion': 'Cr 17M 67B-11 sur Lucero Bajo', 'telefono': '301 467 5377'},
            {'id': 2, 'nombre': 'El Michín Centro',  'direccion': 'Por definir',                    'telefono': 'Por definir'},
        ]

        for data in tiendas_data:
            existente = Tienda.query.filter_by(id=data['id']).first()
            if existente:
                print(f'  Ya existe tienda: {existente.nombre}')
                continue
            tienda = Tienda(**data)
            db.session.add(tienda)
            print(f'  + Tienda: {data["nombre"]}')

        db.session.commit()

        # ---------- USUARIOS ----------
        usuarios_data = [
            {
                'nombre': 'Jean Eduar Sanchez Cañon',
                'username': 'programador',
                'password': 'eduar1985',
                'rol': 'programador',
                'tienda_id': None,
            },
            {
                'nombre': 'Administrador',
                'username': 'admin',
                'password': 'admin123',
                'rol': 'admin',
                'tienda_id': 1,
            },
            {
                'nombre': 'Cajero Tienda 1',
                'username': 'cajero1',
                'password': 'cajero123',
                'rol': 'operario',
                'tienda_id': 1,
            },
            {
                'nombre': 'Cajero Tienda 2',
                'username': 'cajero2',
                'password': 'cajero123',
                'rol': 'operario',
                'tienda_id': 2,
            },
        ]

        for data in usuarios_data:
            existente = Usuario.query.filter_by(username=data['username']).first()
            if existente:
                print(f'  Ya existe usuario: {existente.username}')
                continue
            u = Usuario(
                nombre=data['nombre'],
                username=data['username'],
                password_hash=hash_password(data['password']),
                rol=data['rol'],
                tienda_id=data['tienda_id'],
                activo=True,
            )
            db.session.add(u)
            print(f'  + Usuario: {data["username"]:15s} | rol: {data["rol"]:12s} | pass: {data["password"]}')

        db.session.commit()

        # ---------- RESUMEN ----------
        print('-' * 60)
        print(f'Tiendas totales: {Tienda.query.count()}')
        print(f'Usuarios totales: {Usuario.query.count()}')
        print()
        print('🔑 Credenciales de prueba:')
        print('  programador / eduar1985     (programador - ve todo)')
        print('  admin       / admin123      (admin Tienda 1)')
        print('  cajero1     / cajero123     (operario Tienda 1)')
        print('  cajero2     / cajero123     (operario Tienda 2)')


if __name__ == '__main__':
    crear_datos()