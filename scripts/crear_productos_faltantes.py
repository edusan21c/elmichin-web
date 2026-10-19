import os
import sys
import pandas as pd
import uuid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.tienda import Tienda

app = create_app()
RUTA_EXCEL = os.path.join(BASE_DIR, 'data', 'Codigo Barras productos.xlsx')

# Palabras para ignorar (cigarrillos y los que ya arreglamos)
IGNORAR = ['marlboro', 'lucky', 'rothmans', 'l&m', 'camel', 'winston', 'chesterfield', 'piel roja', 'vuse', 'cherry', 'gudiz']

def crear_faltantes():
    print("--- CREANDO PRODUCTOS FALTANTES EN LA CENTRAL ---")
    df = pd.read_excel(RUTA_EXCEL)
    creados = 0

    with app.app_context():
        nombres_db = {p.nombre.lower().strip(): p for p in Producto.query.all()}
        tiendas = Tienda.query.filter_by(activa=True).all()

        for index, row in df.iterrows():
            barcode = str(row['codigo de barras']).strip()
            nombre = str(row['Producto']).strip()

            if not barcode or barcode.lower() in ['nan', 'na', 'por asignar', '']:
                continue
            if not nombre or nombre.lower() in ['nan', '']:
                continue
            if any(palabra in nombre.lower() for palabra in IGNORAR):
                continue

            nombre_clean = nombre.lower().strip()
            
            # Si NO existe en la Central, lo creamos
            if nombre_clean not in nombres_db:
                # Verificar que el codigo no exista ya en otro producto
                if Producto.query.filter_by(codigo_barras=barcode).first():
                    print(f"AVISO: El codigo {barcode} ya existe para otro producto. Saltando {nombre}.")
                    continue

                try:
                    nuevo_prod = Producto(
                        nombre=nombre,
                        codigo_barras=barcode,
                        categoria='Snacks' if 'papa' in nombre.lower() or 'snack' in nombre.lower() else None,
                        codigo_global=str(uuid.uuid4())
                    )
                    db.session.add(nuevo_prod)
                    db.session.flush()

                    # Crear presentacion en todas las tiendas con stock 0
                    for t in tiendas:
                        pres = ProductoTienda(
                            producto_id=nuevo_prod.id, tienda_id=t.id, cantidad=0,
                            precio_venta=0, precio_venta1=0, precio_venta2=0, precio_venta3=0,
                            sync_estado='pendiente'
                        )
                        db.session.add(pres)

                    creados += 1
                    print(f"CREADO: {nombre} -> {barcode}")
                except Exception as e:
                    db.session.rollback()
                    print(f"ERROR creando {nombre}: {e}")

        db.session.commit()
        print(f"\n--- TERMINADO: {creados} productos nuevos creados con stock 0 ---")

if __name__ == '__main__':
    crear_faltantes()