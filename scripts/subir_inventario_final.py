import os
import sys
import uuid
import pandas as pd
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

app = create_app()
RUTA_EXCEL = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Final.xlsx')

def safe_decimal(val):
    try:
        if pd.isna(val) or val is None or str(val).strip() == '':
            return Decimal('0.00')
        return Decimal(str(val))
    except:
        return Decimal('0.00')

def safe_str(val):
    if pd.isna(val) or val is None:
        return ''
    return str(val).strip()

def safe_int(val):
    try:
        if pd.isna(val) or val is None or str(val).strip() == '':
            return 0
        return int(val)
    except:
        return 0

def actualizar_todo():
    print("--- INICIANDO SUBIDA MASIVA (CORREGIDO) ---")
    
    if not os.path.exists(RUTA_EXCEL):
        print(f"ERROR: No se encuentra el archivo {RUTA_EXCEL}")
        return

    df = pd.read_excel(RUTA_EXCEL, dtype={'Código Barras': str, 'ID (NO TOCAR)': str})
    actualizados = 0
    creados = 0
    errores = 0

    with app.app_context():
        for index, row in df.iterrows():
            prod_id = row.get('ID (NO TOCAR)')
            nombre = safe_str(row.get('Nombre Producto'))
            
            if not nombre:
                continue

            try:
                # Usamos un savepoint (begin_nested) para que si un producto falla, 
                # no dañe los demás y podamos continuar.
                with db.session.begin_nested():
                    if not pd.isna(prod_id) and str(prod_id).strip() != '':
                        # ACTUALIZAR EXISTENTE
                        prod = Producto.query.get(int(prod_id))
                        if prod:
                            prod.nombre = nombre
                            prod.categoria = safe_str(row.get('Categoría')) or None
                            # Solo actualizamos código si no es nulo o vacío
                            nuevo_codigo = safe_str(row.get('Código Barras'))
                            if nuevo_codigo:
                                prod.codigo_barras = nuevo_codigo
                            actualizados += 1
                        else:
                            continue # Si no existe en la BD, lo saltamos
                    else:
                        # CREAR NUEVO
                        nuevo_uuid = str(uuid.uuid4())
                        nuevo_codigo = safe_str(row.get('Código Barras')) or None
                        
                        prod = Producto(
                            nombre=nombre,
                            categoria=safe_str(row.get('Categoría')) or None,
                            codigo_barras=nuevo_codigo,
                            codigo_global=nuevo_uuid  # <-- AQUÍ ESTÁ EL CAMBIO
                        )
                        db.session.add(prod)
                        db.session.flush() # Para obtener el ID
                        creados += 1

                    # Ahora actualizamos/creamos los datos para T1 y T2
                    for tienda_id, prefix in [(1, 'T1'), (2, 'T2')]:
                        pres_t = ProductoTienda.query.filter_by(producto_id=prod.id, tienda_id=tienda_id).first()
                        if not pres_t:
                            pres_t = ProductoTienda(producto_id=prod.id, tienda_id=tienda_id)
                            db.session.add(pres_t)

                        pres_t.cantidad = safe_int(row.get(f'{prefix} Stock'))
                        pres_t.precio_proveedor = safe_decimal(row.get(f'{prefix} Costo'))
                        pres_t.porcentaje = safe_decimal(row.get(f'{prefix} % Gan'))
                        pres_t.precio_venta = safe_decimal(row.get(f'{prefix} Precio Base'))
                        
                        pres_t.condicion1 = safe_str(row.get(f'{prefix} Cond1'))
                        pres_t.precio_venta1 = safe_decimal(row.get(f'{prefix} Precio 1'))
                        pres_t.condicion2 = safe_str(row.get(f'{prefix} Cond2'))
                        pres_t.precio_venta2 = safe_decimal(row.get(f'{prefix} Precio 2'))
                        pres_t.condicion3 = safe_str(row.get(f'{prefix} Cond3'))
                        pres_t.precio_venta3 = safe_decimal(row.get(f'{prefix} Precio 3'))
                        
                        pres_t.sync_estado = 'pendiente'

            except IntegrityError as e:
                # Si hay un producto duplicado (mismo nombre o código), lo saltamos
                errores += 1
                print(f"Saltando '{nombre}': ya existe un producto con ese nombre o código.")
            
        # Guardamos todos los cambios
        db.session.commit()
        print(f"\n--- TERMINADO ---")
        print(f"Productos existentes actualizados: {actualizados}")
        print(f"Productos NUEVOS insertados: {creados}")
        if errores > 0:
            print(f"Productos saltados por duplicados: {errores}")
        print("--- ESPERA 2 MINUTOS PARA QUE EL WORKER ENVIE TODO A T1 Y T2 ---")

if __name__ == '__main__':
    actualizar_todo()