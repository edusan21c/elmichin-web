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

def safe_str(val):
    if pd.isna(val) or val is None:
        return ''
    return str(val).strip().upper()

def eliminar():
    print("--- ELIMINANDO PRODUCTOS FANTASMAS (MODO SEGURO) ---")
    
    df = pd.read_excel(RUTA_EXCEL, dtype={'ID (NO TOCAR)': str, 'Código Barras': str})
    
    # 1. Recolectar todos los IDs, Nombres y Códigos que están en el Excel
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

    print(f"Datos del Excel: {len(ids_excel)} IDs, {len(nombres_excel)} Nombres, {len(codigos_excel)} Códigos.")

    with app.app_context():
        productos_bd = Producto.query.all()
        eliminados = 0
        protegidos = 0
        
        for prod in productos_bd:
            # Si el ID está en el Excel, es un producto existente.
            if prod.id in ids_excel:
                continue
            
            # Si el ID no está, revisamos si el Nombre o el Código están en el Excel (es un producto nuevo)
            nombre_bd = safe_str(prod.nombre)
            codigo_bd = safe_str(prod.codigo_barras)
            
            if (nombre_bd in nombres_excel) or (codigo_bd and codigo_bd in codigos_excel):
                # Es un producto nuevo insertado recientemente. NO SE BORRA.
                protegidos += 1
                continue
            
            # Si llegamos aquí, es un verdadero fantasma.
            print(f"Borrando: {prod.nombre} (ID: {prod.id})")
            db.session.delete(prod)
            eliminados += 1
                
        db.session.commit()
        print(f"\n--- TERMINADO ---")
        print(f"Productos nuevos protegidos (no se borraron): {protegidos}")
        print(f"Productos fantasmas eliminados de la BD: {eliminados}")
        print("Espera 2 minutos para que el Worker actualice T1 y T2.")

if __name__ == '__main__':
    eliminar()