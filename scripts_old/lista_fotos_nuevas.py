import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.models.producto import Producto

app = create_app()
RUTA_EXCEL = os.path.join(BASE_DIR, 'data', 'Codigo Barras productos.xlsx')
RUTA_REPORTE = os.path.join(BASE_DIR, 'data', 'fotos_pendientes_hoy.txt')

# Ignoramos los cigarrillos porque esos ya tienen foto
IGNORAR = ['marlboro', 'lucky', 'rothmans', 'l&m', 'camel', 'winston', 'chesterfield', 'piel roja', 'vuse', 'cherry', 'gudiz']

def generar_lista():
    print("--- GENERANDO LISTA DE FOTOS PENDIENTES (SOLO DEL EXCEL DE HOY) ---")
    
    if not os.path.exists(RUTA_EXCEL):
        print("No se encuentra el Excel.")
        return

    df = pd.read_excel(RUTA_EXCEL)
    pendientes = []

    with app.app_context():
        for index, row in df.iterrows():
            barcode = str(row['codigo de barras']).strip()
            nombre = str(row['Producto']).strip()

            if not barcode or barcode.lower() in ['nan', 'na', 'por asignar', '']:
                continue
            if not nombre or nombre.lower() in ['nan', '']:
                continue
            if any(palabra in nombre.lower() for palabra in IGNORAR):
                continue

            # Buscar el producto en la base de datos
            prod = Producto.query.filter_by(codigo_barras=barcode).first()
            
            # Si el producto existe y NO tiene foto, lo agregamos a la lista
            if prod and not prod.imagen:
                pendientes.append(f"- {prod.nombre} | Codigo: {prod.codigo_barras}")

    # Escribir el archivo
    with open(RUTA_REPORTE, 'w', encoding='utf-8') as f:
        f.write("=== PRODUCTOS NUEVOS O ACTUALIZADOS HOY QUE NECESITAN FOTO ===\n\n")
        for p in pendientes:
            f.write(p + "\n")

    print(f"\nSe encontraron {len(pendientes)} productos sin foto de tu Excel.")
    print(f"Abriendo la lista en el Bloc de Notas...")
    os.startfile(RUTA_REPORTE)

if __name__ == '__main__':
    generar_lista()