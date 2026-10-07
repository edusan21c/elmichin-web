"""
Asegura que las extensiones PostgreSQL requeridas existan.
Idempotente: si ya estan, no rompe. Si faltan, las crea.

Corre en cada update (via actualizar_sistema.py) para que las tiendas
nuevas (T2, T3...) no tengan sorpresas tipo "unaccent does not exist".
"""
import os
import sys

# Cargar .env de la raiz del proyecto
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, '.env'))
except ImportError:
    print('Aviso: python-dotenv no instalado, leo variables del entorno')

import psycopg2

EXTENSIONES_REQUERIDAS = ['unaccent']


def main():
    db_name = os.getenv('DB_NAME') or os.getenv('DB_DATABASE')
    db_user = os.getenv('DB_USER', 'postgres')
    db_pass = os.getenv('DB_PASSWORD', '')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')

    if not db_name:
        print('ERROR: DB_NAME no configurado en .env')
        sys.exit(1)

    print(f'Conectando a {db_host}:{db_port}/{db_name} como {db_user}...')

    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_pass,
        )
    except Exception as e:
        print(f'ERROR conectando a PostgreSQL: {e}')
        sys.exit(1)

    try:
        cur = conn.cursor()
        for ext in EXTENSIONES_REQUERIDAS:
            try:
                cur.execute(f'CREATE EXTENSION IF NOT EXISTS {ext};')
                conn.commit()
                print(f'OK: {ext}')
            except Exception as e:
                print(f'ERROR creando {ext}: {e}')
                conn.rollback()
                # No es fatal: seguimos con las demas
        cur.close()
    finally:
        conn.close()

    print('Extensiones aseguradas.')


if __name__ == '__main__':
    main()