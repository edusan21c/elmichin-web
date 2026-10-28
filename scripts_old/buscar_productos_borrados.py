import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.extensions import db
from app.models.producto import Producto

app = create_app()
RUTA_EXCEL = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Final.xlsx')

def buscar_borrados():
    print("--- BUSCANDO PRODUCTOS QUE ESTÁN EN LA BD PERO NO EN EL EXCEL ---")
    
    df = pd.read_excel(RUTA_EXCEL, dtype={'ID (NO TOCAR)': str})
    
    ids_en_excel = set()
    for _, row in df.iterrows():
        pid = row.get('ID (NO TOCAR)')
        if pd.notna(pid) and str(pid).strip() != '' and str(pid).strip() != 'nan':
            ids_en_excel.add(int(pid))

    print(f"IDs encontrados en el Excel: {len(ids_en_excel)}")

    with app.app_context():
        productos_bd = Producto.query.all()
        fantasmas = []
        for prod in productos_bd:
            if prod.id not in ids_en_excel:
                fantasmas.append(prod)

        print(f"Productos en la BD que NO están en el Excel: {len(fantasmas)}")
        
        if len(fantasmas) > 0:
            print("\nLista de productos a borrar:")
            for f in fantasmas:
                print(f"ID: {f.id} | Nombre: {f.nombre} | Código: {f.codigo_barras}")
        else:
            print("\n¡Excelente! No hay productos 'fantasmas'. El Excel y la BD están sincronizados.")

if __name__ == '__main__':
    buscar_borrados()