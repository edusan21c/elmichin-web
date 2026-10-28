import os
import sys
import pandas as pd
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

app = create_app()
RUTA_EXCEL = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Completo.xlsx')

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

def actualizar_todo():
    print("--- INICIANDO ACTUALIZACION MASIVA DESDE EL EXCEL ---")
    
    if not os.path.exists(RUTA_EXCEL):
        print(f"ERROR: No se encuentra el archivo {RUTA_EXCEL}")
        return

    df = pd.read_excel(RUTA_EXCEL)
    actualizados = 0
    no_encontrados = 0

    with app.app_context():
        for index, row in df.iterrows():
            prod_id = row.get('ID (NO TOCAR)')
            
            # Si la fila no tiene ID, la ignoramos (es un producto nuevo que agregaste al final)
            if pd.isna(prod_id):
                continue

            prod = Producto.query.get(int(prod_id))
            if not prod:
                no_encontrados += 1
                continue

            # 1. Actualizar datos globales del producto
            prod.nombre = safe_str(row.get('Nombre Producto'))
            prod.categoria = safe_str(row.get('Categoría')) or None
            prod.codigo_barras = safe_str(row.get('Código Barras')) or None

            # 2. Actualizar Tienda 1
            pres_t1 = ProductoTienda.query.filter_by(producto_id=prod.id, tienda_id=1).first()
            if pres_t1:
                pres_t1.cantidad = int(row.get('T1 Stock', 0)) if not pd.isna(row.get('T1 Stock')) else 0
                pres_t1.precio_proveedor = safe_decimal(row.get('T1 Costo'))
                pres_t1.porcentaje = safe_decimal(row.get('T1 % Gan'))
                pres_t1.precio_venta = safe_decimal(row.get('T1 Precio Base'))
                pres_t1.condicion1 = safe_str(row.get('T1 Cond1'))
                pres_t1.precio_venta1 = safe_decimal(row.get('T1 Precio 1'))
                pres_t1.condicion2 = safe_str(row.get('T1 Cond2'))
                pres_t1.precio_venta2 = safe_decimal(row.get('T1 Precio 2'))
                pres_t1.condicion3 = safe_str(row.get('T1 Cond3'))
                pres_t1.precio_venta3 = safe_decimal(row.get('T1 Precio 3'))
                pres_t1.sync_estado = 'pendiente' # Para que el worker se lo lleve

            # 3. Actualizar Tienda 2
            pres_t2 = ProductoTienda.query.filter_by(producto_id=prod.id, tienda_id=2).first()
            if pres_t2:
                pres_t2.cantidad = int(row.get('T2 Stock', 0)) if not pd.isna(row.get('T2 Stock')) else 0
                pres_t2.precio_proveedor = safe_decimal(row.get('T2 Costo'))
                pres_t2.porcentaje = safe_decimal(row.get('T2 % Gan'))
                pres_t2.precio_venta = safe_decimal(row.get('T2 Precio Base'))
                pres_t2.condicion1 = safe_str(row.get('T2 Cond1'))
                pres_t2.precio_venta1 = safe_decimal(row.get('T2 Precio 1'))
                pres_t2.condicion2 = safe_str(row.get('T2 Cond2'))
                pres_t2.precio_venta2 = safe_decimal(row.get('T2 Precio 2'))
                pres_t2.condicion3 = safe_str(row.get('T2 Cond3'))
                pres_t2.precio_venta3 = safe_decimal(row.get('T2 Precio 3'))
                pres_t2.sync_estado = 'pendiente'

            actualizados += 1

        db.session.commit()
        print(f"\n--- TERMINADO: {actualizados} productos actualizados exitosamente ---")
        print(f"--- Productos del Excel no encontrados en la BD: {no_encontrados} ---")
        print("--- ESPERA 2 MINUTOS PARA QUE EL WORKER ENVIE TODO A T1 Y T2 ---")

if __name__ == '__main__':
    actualizar_todo()