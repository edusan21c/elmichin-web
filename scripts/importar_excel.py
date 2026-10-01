# scripts/importar_excel.py
# Importa productos desde data/productos.xlsx a PostgreSQL.
# Uso:  python scripts\importar_excel.py
#
# Formato esperado del Excel (Hoja1):
# A: Nombre | B: Precio normal | C: Mayor 1 | D: Mayor 2
# E: Cond 1 | F: Cond 2 | G: Cond 3
#
# Idempotente: si un producto ya existe, se OMITE.

import os
import sys
import hashlib
from decimal import Decimal, ROUND_HALF_UP

import openpyxl

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.tienda import Tienda

RUTA_EXCEL = os.path.join(RAIZ, 'data', 'productos.xlsx')
STOCK_INICIAL = 0
MARGEN_ESTIMADO = Decimal('0.15')  # 15% por defecto para estimar costo


def limpiar_numero(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return Decimal(str(v))
        except Exception:
            return None
    if isinstance(v, str):
        v = v.strip().replace(',', '').replace('$', '').replace(' ', '')
        if not v:
            return None
        try:
            return Decimal(v)
        except Exception:
            return None
    return None


def generar_codigo_unico(nombre, existentes):
    base = hashlib.sha256(nombre.encode('utf-8')).hexdigest()[:12]
    codigo = base
    intento = 0
    while codigo in existentes:
        intento += 1
        codigo = f'{base[:10]}{intento:02d}'
    return codigo


def categoria_por_nombre(nombre):
    n = nombre.lower()
    if any(x in n for x in ['papa ', 'papas', 'detodito', 'dorito', 'takis', 'cheetos', 'choclito', 'cheestris']):
        return 'snack'
    if any(x in n for x in ['coca', 'pepsi', 'postobon', 'gaseosa', 'jugo', 'hit', 'agua', 'gatorade', 'red bull', 'monster', 'poker', 'aguila', 'corona']):
        return 'bebida'
    if any(x in n for x in ['marlboro', 'lucky', 'camel', 'chesterfield', 'lm ', 'l&m', 'winston', 'piel roja', 'rothmans']):
        return 'cigarro'
    if any(x in n for x in ['cerveza', 'ron ', 'vodka', 'whisky', 'tequila', 'aguardiente', 'smirnoff', 'bacardí', 'bacardi']):
        return 'licor'
    if any(x in n for x in ['papel', 'jabon', 'jabón', 'shampoo', 'clorox', 'toalla', 'servilleta']):
        return 'aseo'
    return 'dulce'


def main():
    if not os.path.exists(RUTA_EXCEL):
        print(f'[ERROR] No existe: {RUTA_EXCEL}')
        print('Copia el Excel a data/productos.xlsx y vuelve a ejecutar.')
        return

    print(f'Leyendo {RUTA_EXCEL} ...')
    wb = openpyxl.load_workbook(RUTA_EXCEL, data_only=True)
    hoja = wb.active
    print(f'Hoja activa: {hoja.title}')

    app = create_app()
    with app.app_context():
        tiendas = Tienda.query.filter_by(activa=True).order_by(Tienda.id).all()
        if not tiendas:
            print('[ERROR] No hay tiendas activas.')
            return
        print(f'Tiendas destino: {[t.nombre for t in tiendas]}')

        # Recopilar codigos existentes
        existentes_codigos = {p.codigo_barras for p in Producto.query.all() if p.codigo_barras}
        existentes_nombres = {p.nombre.lower() for p in Producto.query.all()}

        nuevos = 0
        omitidos = 0
        errores = 0
        filas_totales = 0

        for idx, fila in enumerate(hoja.iter_rows(min_row=2, values_only=True), start=2):
            if not fila or not fila[0]:
                continue
            nombre = str(fila[0]).strip()
            if not nombre:
                continue
            filas_totales += 1

            if nombre.lower() in existentes_nombres:
                omitidos += 1
                continue

            precio_normal = limpiar_numero(fila[1])
            precio_mayor1 = limpiar_numero(fila[2])
            precio_mayor2 = limpiar_numero(fila[3])
            cond1 = str(fila[4]).strip() if len(fila) > 4 and fila[4] not in (None, '') else ''
            cond2 = str(fila[5]).strip() if len(fila) > 5 and fila[5] not in (None, '') else ''
            cond3 = str(fila[6]).strip() if len(fila) > 6 and fila[6] not in (None, '') else ''

            # Limpiar condiciones (a veces vienen como float 3.0)
            def limpiar_cond(c):
                try:
                    return str(int(float(c)))
                except Exception:
                    return ''
            cond1 = limpiar_cond(cond1)
            cond2 = limpiar_cond(cond2)
            cond3 = limpiar_cond(cond3)

            if not precio_normal or precio_normal <= 0:
                errores += 1
                continue

            # Precio proveedor estimado (asumiendo 15% margen)
            precio_prov = (precio_normal * (Decimal('1') - MARGEN_ESTIMADO)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            # Descuentos calculados
            def descuento_pct(precio):
                if not precio or precio <= 0 or precio >= precio_normal:
                    return Decimal('0')
                d = ((precio_normal - precio) / precio_normal) * Decimal('100')
                return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            d1 = descuento_pct(precio_mayor1)
            d2 = descuento_pct(precio_mayor2)

            # Codigo unico
            codigo = generar_codigo_unico(nombre, existentes_codigos)
            existentes_codigos.add(codigo)

            # Crear producto
            producto = Producto(
                nombre=nombre,
                codigo_barras=codigo,
                categoria=categoria_por_nombre(nombre),
            )
            db.session.add(producto)
            db.session.flush()

            # Crear presentacion en cada tienda
            for tienda in tiendas:
                pres = ProductoTienda(
                    producto_id=producto.id,
                    tienda_id=tienda.id,
                    cantidad=STOCK_INICIAL,
                    precio_proveedor=precio_prov,
                    precio_proveedor2=precio_prov,
                    precio_proveedor3=precio_prov,
                    porcentaje=Decimal('15.00'),
                    precio_venta=precio_normal,
                    descuento1_porcentaje=d1,
                    precio_venta1=precio_mayor1 or Decimal('0'),
                    descuento2_porcentaje=d2,
                    precio_venta2=precio_mayor2 or Decimal('0'),
                    descuento3_porcentaje=Decimal('0'),
                    precio_venta3=Decimal('0'),
                    condicion1=cond1,
                    condicion2=cond2,
                    condicion3=cond3,
                )
                db.session.add(pres)

            existentes_nombres.add(nombre.lower())
            nuevos += 1

            if nuevos % 50 == 0:
                db.session.commit()
                print(f'  ... {nuevos} productos importados')

        db.session.commit()

        print()
        print('=' * 60)
        print(f'  Filas procesadas: {filas_totales}')
        print(f'  Importados:      {nuevos}')
        print(f'  Omitidos (ya existian): {omitidos}')
        print(f'  Errores (sin precio):   {errores}')
        print('=' * 60)
        print(f'Total productos en BD: {Producto.query.count()}')


if __name__ == '__main__':
    main()