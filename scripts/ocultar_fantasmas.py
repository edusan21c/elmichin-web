import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

app = create_app()
RUTA_EXCEL = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Final.xlsx')

def safe_str(val):
    if pd.isna(val) or val is None:
        return ''
    return str(val).strip().upper()

def ocultar():
    print("--- OCULTANDO PRODUCTOS FANTASMAS (MODO SEGURO) ---")
    
    df = pd.read_excel(RUTA_EXCEL, dtype={'ID (NO TOCAR)': str, 'Código Barras': str})
    
    ids_excel = set()
    nombres_excel = set()
    codigos_excel = set()

    for _, row in df.iterrows():
        pid = row.get('ID (NO TOCAR)')
        if pd.notna(pid) and str(pid).strip() not in ('', 'nan'):
            ids_excel.add(int(pid))
        
        nombre = safe_str(row.get('Nombre Producto'))
        if nombre: nombres_excel.add(nombre)
        
        codigo = safe_str(row.get('Código Barras'))
        if codigo and codigo != 'NAN': codigos_excel.add(codigo)

    with app.app_context():
        productos_bd = Producto.query.all()
        ocultos = 0
        
        for prod in productos_bd:
            if prod.id in ids_excel:
                continue
            
            nombre_bd = safe_str(prod.nombre)
            codigo_bd = safe_str(prod.codigo_barras)
            
            # Si el nombre o el código están en el Excel, es nuevo. No se toca.
            if (nombre_bd in nombres_excel) or (codigo_bd and codigo_bd in codigos_excel):
                continue
            
            # Si llegamos aquí, es un fantasma. Lo pasamos a INACTIVO y stock 0.
            print(f"Ocultando: {prod.nombre} (ID: {prod.id})")
            prod.categoria = "INACTIVO"
            
            for pres in prod.presentaciones:
                pres.cantidad = 0
                pres.sync_estado = 'pendiente' # Para que el worker actualice las tiendas
                
            ocultos += 1
                
        db.session.commit()
        print(f"\n--- TERMINADO ---")
        print(f"Productos movidos a la categoría INACTIVO: {ocultos}")
        print("Espera 2 minutos para que T1 y T2 se actualicen.")

if __name__ == '__main__':
    ocultar()