import os
import sys
import pandas as pd

# Configurar rutas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.models.producto import Producto

app = create_app()
RUTA_EXCEL = os.path.join(BASE_DIR, 'data', 'Codigo Barras productos.xlsx')
RUTA_REPORTE = os.path.join(BASE_DIR, 'data', 'reporte_auditoria.txt')

def auditar():
    print("--- INICIANDO AUDITORIA (SOLO LECTURA, NO CAMBIA NADA) ---")
    
    if not os.path.exists(RUTA_EXCEL):
        print(f"ERROR: No se encuentra el archivo en {RUTA_EXCEL}")
        return

    df = pd.read_excel(RUTA_EXCEL)

    coincidencias_exactas = []
    no_encontrados = []
    codigos_repetidos = set()
    codigos_vistos = set()

    with app.app_context():
        # Traemos todos los productos de la Central a la memoria
        productos_db = {p.nombre.lower().strip(): p for p in Producto.query.all()}

        for index, row in df.iterrows():
            barcode = str(row['codigo de barras']).strip()
            nombre = str(row['Producto']).strip()

            # Ignorar vacios o "Na"
            if not barcode or barcode.lower() in ['nan', 'na', 'por asignar', '']:
                continue
            if not nombre or nombre.lower() in ['nan', '']:
                continue

            if barcode in codigos_vistos:
                codigos_repetidos.add(barcode)
            codigos_vistos.add(barcode)

            nombre_clean = nombre.lower().strip()
            
            # Buscar si el nombre es EXACTAMENTE igual en la base de datos
            if nombre_clean in productos_db:
                prod = productos_db[nombre_clean]
                # Si el código es diferente al que ya tiene, es un candidato a actualizar
                if prod.codigo_barras != barcode:
                    coincidencias_exactas.append(f"{nombre} -> {barcode} (Antes tenia: {prod.codigo_barras})")
            else:
                no_encontrados.append(f"{nombre} (Codigo Excel: {barcode})")

        # Escribir reporte en un archivo de texto
        with open(RUTA_REPORTE, 'w', encoding='utf-8') as f:
            f.write("=== COINCIDENCIAS EXACTAS (Seguros de cambiar) ===\n")
            for c in coincidencias_exactas:
                f.write(c + "\n")
            
            f.write(f"\n=== NO ENCONTRADOS EN LA CENTRAL ({len(no_encontrados)}) ===\n")
            for n in no_encontrados:
                f.write(n + "\n")

            f.write(f"\n=== CODIGOS DUPLICADOS EN EL EXCEL ({len(codigos_repetidos)}) ===\n")
            for c in codigos_repetidos:
                f.write(c + "\n")

        print("\n--- AUDITORIA TERMINADA ---")
        print(f"Se encontraron {len(coincidencias_exactas)} coincidencias EXACTAS (seguras de cambiar).")
        print(f"Se encontraron {len(no_encontrados)} productos que NO estan en la Central.")
        print(f"Se encontraron {len(codigos_repetidos)} codigos repetidos en el Excel.")
        print(f"\nRevisa el archivo de reporte aqui: {RUTA_REPORTE}")

if __name__ == '__main__':
    auditar()