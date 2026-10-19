import os
import sys
import pandas as pd
import difflib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.models.producto import Producto

app = create_app()
RUTA_EXCEL = os.path.join(BASE_DIR, 'data', 'Codigo Barras productos.xlsx')
RUTA_REPORTE = os.path.join(BASE_DIR, 'data', 'sugerencias_fase2.txt')

# Palabras para ignorar los cigarrillos
IGNORAR = ['marlboro', 'lucky', 'rothmans', 'l&m', 'camel', 'winston', 'chesterfield', 'piel roja', 'vuse', 'cherry', 'gudiz']

def sugerir():
    print("--- GENERANDO SUGERENCIAS FASE 2 (SOLO LECTURA) ---")
    df = pd.read_excel(RUTA_EXCEL)

    with app.app_context():
        nombres_db = [p.nombre for p in Producto.query.all()]
        nombres_db_lower = [n.lower() for n in nombres_db]

        with open(RUTA_REPORTE, 'w', encoding='utf-8') as f:
            f.write("=== SUGERENCIAS DE EMPAREJAMIENTO (SIN CIGARRILLOS) ===\n\n")
            
            for index, row in df.iterrows():
                barcode = str(row['codigo de barras']).strip()
                nombre = str(row['Producto']).strip()

                if not barcode or barcode.lower() in ['nan', 'na', 'por asignar', '']:
                    continue
                if not nombre or nombre.lower() in ['nan', '']:
                    continue

                # 1. Ignorar cigarrillos
                if any(palabra in nombre.lower() for palabra in IGNORAR):
                    continue

                # 2. Si ya existe exacto, ignorar
                if nombre.lower() in nombres_db_lower:
                    continue 

                # 3. Buscar sugerencias (nombres parecidos)
                sugerencias = difflib.get_close_matches(nombre.lower(), nombres_db_lower, n=2, cutoff=0.4)
                
                if sugerencias:
                    f.write(f"EXCEL: {nombre} (Codigo: {barcode})\n")
                    for sug in sugerencias:
                        idx = nombres_db_lower.index(sug)
                        f.write(f"  -> POSIBLE EN CENTRAL: {nombres_db[idx]}\n")
                    f.write("\n")
                else:
                    f.write(f"EXCEL: {nombre} (Codigo: {barcode}) -> NO HAY SUGERENCIAS CLARAS\n\n")

    print(f"--- REPORTE GENERADO EN: {RUTA_REPORTE} ---")

if __name__ == '__main__':
    sugerir()