import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

app = create_app()
RUTA_EXCEL = os.path.join(BASE_DIR, 'data', 'Codigo Barras productos.xlsx')

# Estos son los codigos que sabemos que estan duplicados y NO vamos a tocar
DUPLICADOS = {
    '7702005602427', '7702005600157', '7702005002357', '7702303611862', 
    '7702303097475', '7702303809221', '77063342', '7702303006651', 
    '7702303607223', '7702007088410', '7702303842341', '7702005917712', 
    '7702303006347', '7702303953863', '7702152109701', '7702152109695', 
    '7702303795661', '7702005602144'
}

def aplicar():
    print("--- APLICANDO CAMBIOS SEGUROS ---")
    df = pd.read_excel(RUTA_EXCEL)
    actualizados = 0

    with app.app_context():
        # Cargamos todos los productos de la Central
        productos_db = {p.nombre.lower().strip(): p for p in Producto.query.all()}

        for index, row in df.iterrows():
            barcode = str(row['codigo de barras']).strip()
            nombre = str(row['Producto']).strip()

            if not barcode or barcode.lower() in ['nan', 'na', 'por asignar', '']:
                continue
            if not nombre or nombre.lower() in ['nan', '']:
                continue
            if barcode in DUPLICADOS:
                continue # Nos saltamos los duplicados para no romper la DB

            nombre_clean = nombre.lower().strip()
            
            if nombre_clean in productos_db:
                prod = productos_db[nombre_clean]
                if prod.codigo_barras != barcode:
                    prod.codigo_barras = barcode
                    # Marcar para sincronizar a las tiendas
                    ProductoTienda.query.filter_by(producto_id=prod.id).update({'sync_estado': 'pendiente'})
                    actualizados += 1
                    print(f"OK: {nombre} -> {barcode}")

        db.session.commit()
        print(f"\n--- TERMINADO: {actualizados} productos actualizados de forma segura ---")

if __name__ == '__main__':
    aplicar()