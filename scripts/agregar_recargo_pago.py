# scripts/agregar_recargo_pago.py
# Agrega la columna 'recargo' a la tabla pagos.
# Idempotente. Ejecutar: python scripts\agregar_recargo_pago.py
import os
import sys
import psycopg2

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leer_env():
    config = {}
    with open(os.path.join(RAIZ, '.env'), 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()
    return config


def migrar_bd(nombre_bd, config):
    print(f'\n=== Migrando {nombre_bd} ===')
    try:
        conn = psycopg2.connect(
            host=config.get('DB_HOST', 'localhost'),
            port=config.get('DB_PORT', '5432'),
            user=config.get('DB_USER', 'postgres'),
            password=config.get('DB_PASSWORD', ''),
            database=nombre_bd,
        )
        conn.autocommit = True
        cur = conn.cursor()

        try:
            cur.execute("ALTER TABLE pagos ADD COLUMN recargo NUMERIC(12, 2) DEFAULT 0;")
            print('  ✅ Columna recargo agregada')
        except psycopg2.errors.DuplicateColumn:
            print('  ⚠️  Columna recargo ya existe (OK)')

        cur.execute("SELECT COUNT(*) FROM pagos;")
        total = cur.fetchone()[0]
        print(f'  📊 Total pagos: {total}')

        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f'  ❌ ERROR: {e}')
        return False


def main():
    config = leer_env()
    modo = config.get('MODO', 'tienda_local')
    db_name = config.get('DB_NAME', 'michin_central')

    print('=' * 60)
    print('AGREGAR COLUMNA recargo A pagos')
    print('=' * 60)
    print(f'Modo: {modo} | BD: {db_name}')

    dbs = ['michin_central', 'michin_t1', 'michin_t2'] if modo == 'central' else [db_name]

    ok = 0
    for db in dbs:
        try:
            conn_test = psycopg2.connect(
                host=config.get('DB_HOST', 'localhost'),
                port=config.get('DB_PORT', '5432'),
                user=config.get('DB_USER', 'postgres'),
                password=config.get('DB_PASSWORD', ''),
                database='postgres',
            )
            conn_test.autocommit = True
            cur = conn_test.cursor()
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db,))
            existe = cur.fetchone() is not None
            cur.close()
            conn_test.close()
            if not existe:
                print(f'\n=== {db} ===\n  ⚠️  BD no existe (salto)')
                continue
        except Exception as e:
            print(f'\n=== {db} ===\n  ⚠️  {e}')
            continue

        if migrar_bd(db, config):
            ok += 1

    print(f'\nMIGRACIÓN COMPLETADA: {ok} BD(s)')


if __name__ == '__main__':
    main()