# scripts/importar_t2.py
import os
import sys
import openpyxl
from decimal import Decimal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda

RUTA_EXCEL = os.path.join(RAIZ, 'data', 'B. Datos tienda michin B.xlsx')

def limpiar_numero(v):
    if v is None or v == '':
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None

def main():
    app = create_app()
    with app.app_context():
        print(f"Leyendo archivo: {RUTA_EXCEL}")
        if not os.path.exists(RUTA_EXCEL):
            print("ERROR: No se encontró el archivo Excel.")
            return

        wb = openpyxl.load_workbook(RUTA_EXCEL, data_only=True)
        sheet = wb.active
        
        actualizados = 0
        no_encontrados = []

        for i, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not row or not row[0]:
                continue
                
            nombre = str(row[0]).strip()
            precio_normal = limpiar_numero(row[1])
            mayor1 = limpiar_numero(row[2])
            mayor2 = limpiar_numero(row[3])
            cond1 = limpiar_numero(row[4])
            cond2 = limpiar_numero(row[5])
            cond3 = limpiar_numero(row[6]) if len(row) > 6 else None

            prod = Producto.query.filter_by(nombre=nombre).first()
            if not prod:
                prod = Producto.query.filter(Producto.nombre.ilike(nombre)).first()

            if prod:
                pt = ProductoTienda.query.filter_by(producto_id=prod.id, tienda_id=2).first()
                if pt:
                    if precio_normal is not None: pt.precio_venta = precio_normal
                    if mayor1 is not None: pt.precio_venta1 = mayor1
                    if mayor2 is not None: pt.precio_venta2 = mayor2
                    if cond1 is not None: pt.condicion1 = int(cond1)
                    if cond2 is not None: pt.condicion2 = int(cond2)
                    if cond3 is not None: pt.condicion3 = int(cond3)
                    
                    # Marcar para que T2 lo descargue en el próximo sync
                    pt.sync_estado = 'pendiente'
                    pt.sync_fecha = None
                    actualizados += 1
            else:
                no_encontrados.append(nombre)

        db.session.commit()
        print(f"--- ACTUALIZADOS CON EXITO: {actualizados} productos ---")
        if no_encontrados:
            print(f"--- OJO, NO ENCONTRADOS EN EL SISTEMA: {len(no_encontrados)} ---")
            for n in no_encontrados[:10]: # Mostrar solo los primeros 10
                print(f" - {n}")

if __name__ == '__main__':
    main()