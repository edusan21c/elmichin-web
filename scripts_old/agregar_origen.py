# scripts/agregar_origen.py
# Agrega la columna 'origen' a la tabla facturas en las BDs locales.
# Ejecutar UNA VEZ en CADA PC (central, tienda 1, tienda 2).
# Uso: python scripts\agregar_origen.py

import os
import sys
import psycopg2

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leer_env():
    env_path = os.path.join(RAIZ, '.env')
    config = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip()
    return config


def bd_existe(config, nombre_bd):
    """Verifica si una BD existe en el servidor PostgreSQL local."""
    try:
        conn = psycopg2.connect(
            host=config.get('DB_HOST', 'localhost'),
            port=config.get('DB_PORT', '5432'),
            user=config.get('DB_USER', 'postgres'),
            password=config.get('DB_PASSWORD', ''),
            database='postgres',
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (nombre_bd,))
        existe = cur.fetchone() is not None
        cur.close()
        conn.close()
        return existe
    except Exception as e:
        print(f'  ⚠️  No se pudo verificar {nombre_bd}: {e}')
        return False


def migrar_bd(config, nombre_bd):
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
        cursor = conn.cursor()

        # 1. Agregar columna si no existe
        try:
            cursor.execute("ALTER TABLE facturas ADD COLUMN origen VARCHAR(20) DEFAULT 'local';")
            print('  ✅ Columna "origen" agregada')
        except psycopg2.errors.DuplicateColumn:
            print('  ⚠️  Columna "origen" ya existía (OK)')
        except Exception as e:
            print(f'  ❌ Error agregando columna: {e}')
            cursor.close()
            conn.close()
            return False

        # 2. Crear índice
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_facturas_origen ON facturas(origen);")
        print('  ✅ Índice ix_facturas_origen creado')

        # 3. Verificar estructura
        cursor.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'facturas' AND column_name = 'origen';
        """)
        fila = cursor.fetchone()
        if fila:
            print(f'  ✅ Verificado: {fila[0]} | {fila[1]} | default={fila[2]}')
        else:
            print('  ❌ ERROR: columna no encontrada después del ALTER')
            cursor.close()
            conn.close()
            return False

        # 4. Contar facturas
        cursor.execute("SELECT COUNT(*) FROM facturas;")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM facturas WHERE origen = 'local';")
        locales = cursor.fetchone()[0]
        print(f'  📊 Total facturas: {total} (marcadas como local: {locales})')

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f'  ❌ ERROR conectando: {e}')
        return False


def main():
    print('=' * 60)
    print('AGREGAR COLUMNA "origen" A LA TABLA facturas')
    print('=' * 60)

    config = leer_env()
    modo = config.get('MODO', 'tienda_local')
    db_name = config.get('DB_NAME', 'michin_central')

    print(f'Modo detectado: {modo}')
    print(f'BD principal:   {db_name}')

    if modo == 'central':
        # En el central: intentar migrar todas las BDs conocidas
        candidatas = ['michin_central', 'michin_t1', 'michin_t2']
    else:
        # En la tienda: solo la BD local
        candidatas = [db_name]

    exitos = 0
    for db in candidatas:
        if not bd_existe(config, db):
            print(f'\n=== {db} ===')
            print('  ⚠️  BD no existe en este servidor (saltando)')
            continue
        if migrar_bd(config, db):
            exitos += 1

    print()
    print('=' * 60)
    print(f'MIGRACIÓN COMPLETADA: {exitos} BD(s) migradas exitosamente')
    print('=' * 60)
    print()
    print('⚠️  RECORDATORIO:')
    print('  Ejecuta este script TAMBIÉN en las PCs de las tiendas')
    print('  (cada PC tiene su propio PostgreSQL)')


if __name__ == '__main__':
    main()