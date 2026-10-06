# scripts/importar_excel.py
# Importa productos desde data/productos.xlsx a PostgreSQL.
# Uso normal:    python scripts\importar_excel.py
# Uso con reset: python scripts\importar_excel.py --reset
#
# Formato esperado del Excel (Hoja1):
# A: Nombre | B: Precio normal | C: Mayor 1 | D: Mayor 2
# E: Cond 1 | F: Cond 2 | G: Cond 3

import argparse
import os
import sys
import hashlib
from decimal import Decimal, ROUND_HALF_UP

import openpyxl

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.extensions import db
from app.models.factura import Factura, DetalleFactura
from app.models.cliente import Cliente
from app.models.pago import Pago
from app.models.producto import Producto, ProductoTienda
from app.models.tienda import Tienda

RUTA_EXCEL = os.path.join(RAIZ, 'data', 'productos.xlsx')
STOCK_INICIAL = 0
MARGEN_ESTIMADO = Decimal('0.15')


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


def redondear_entero(v):
    """Redondea al entero mas cercano."""
    if v is None:
        return None
    return v.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


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
    if any(x in n for x in ['cerveza', 'ron ', 'vodka', 'whisky', 'tequila', 'aguardiente', 'smirnoff', 'bacardi']):
        return 'licor'
    if any(x in n for x in ['papel', 'jabon', 'shampoo', 'clorox', 'toalla', 'servilleta']):
        return 'aseo'
    return 'dulce'


def limpiar_cond(c):
    try:
        return str(int(float(c)))
    except Exception:
        return ''


def purgar_datos():
    """Borra TODA la data operativa: ventas, facturas, pagos, clientes, productos."""
    print('  Borrando ventas...')
    n = db.session.execute(db.text('DELETE FROM ventas')).rowcount
    print(f'    {n} filas')

    print('  Borrando detalle_factura...')
    n = db.session.query(DetalleFactura).delete()
    print(f'    {n} filas')

    print('  Borrando pagos...')
    n = db.session.query(Pago).delete()
    print(f'    {n} filas')

    print('  Borrando facturas...')
    n = db.session.query(Factura).delete()
    print(f'    {n} filas')

    print('  Borrando clientes...')
    n = db.session.query(Cliente).delete()
    print(f'    {n} filas')

    print('  Borrando producto_tienda...')
    n = db.session.query(ProductoTienda).delete()
    print(f'    {n} filas')

    print('  Borrando productos...')
    n = db.session.query(Producto).delete()
    print(f'    {n} filas')

    db.session.commit()


def main(reset=False, skip_confirm=False):
    if not os.path.exists(RUTA_EXCEL):
        print(f'[ERROR] No existe: {RUTA_EXCEL}')
        return

    app = create_app()
    with app.app_context():
        print(f'Base de datos: {db.engine.url.database}')

        if reset:
            print()
            print('=' * 60)
            print('  MODO RESET -- se BORRARA toda la data operativa')
            print('=' * 60)

            if not skip_confirm:
                respuesta = input('Escribi SI (mayusculas) para confirmar: ')
                if respuesta.strip() != 'SI':
                    print('Cancelado por el usuario.')
                    return

            purgar_datos()
            print('  [OK] Purga completada.')

        print()
        print(f'Leyendo {RUTA_EXCEL} ...')
        wb = openpyxl.load_workbook(RUTA_EXCEL, data_only=True)
        hoja = wb.active
        print(f'Hoja activa: {hoja.title}')

        tiendas = Tienda.query.filter_by(activa=True).order_by(Tienda.id).all()
        if not tiendas:
            print('[ERROR] No hay tiendas activas.')
            return
        print(f'Tiendas destino: {[t.nombre for t in tiendas]}')

        existentes_codigos = set()
        existentes_nombres = set()

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
            cond1 = limpiar_cond(fila[4]) if len(fila) > 4 else ''
            cond2 = limpiar_cond(fila[5]) if len(fila) > 5 else ''
            cond3 = limpiar_cond(fila[6]) if len(fila) > 6 else ''

            # Productos sin precio: crear con 0 (decision del usuario)
            if precio_normal is None or precio_normal < 0:
                precio_normal = Decimal('0')

            # Redondear precios al entero mas cercano
            precio_normal = redondear_entero(precio_normal)
            precio_mayor1 = redondear_entero(precio_mayor1) if precio_mayor1 else Decimal('0')
            precio_mayor2 = redondear_entero(precio_mayor2) if precio_mayor2 else Decimal('0')

            # Precio proveedor estimado
            if precio_normal > 0:
                precio_prov = (precio_normal * (Decimal('1') - MARGEN_ESTIMADO)).quantize(
                    Decimal('1'), rounding=ROUND_HALF_UP
                )
            else:
                precio_prov = Decimal('0')

            def descuento_pct(precio):
                if not precio or precio <= 0 or precio >= precio_normal or precio_normal == 0:
                    return Decimal('0')
                d = ((precio_normal - precio) / precio_normal) * Decimal('100')
                return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            d1 = descuento_pct(precio_mayor1)
            d2 = descuento_pct(precio_mayor2)

            codigo = generar_codigo_unico(nombre, existentes_codigos)
            existentes_codigos.add(codigo)

            producto = Producto(
                nombre=nombre,
                codigo_barras=codigo,
                categoria=categoria_por_nombre(nombre),
            )
            db.session.add(producto)
            db.session.flush()

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
                    precio_venta1=precio_mayor1,
                    descuento2_porcentaje=d2,
                    precio_venta2=precio_mayor2,
                    descuento3_porcentaje=Decimal('0'),
                    precio_venta3=Decimal('0'),
                    condicion1=cond1,
                    condicion2=cond2,
                    condicion3=cond3,
                    sync_estado='sincronizado',
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
        print(f'  Omitidos:        {omitidos}')
        print(f'  Errores:         {errores}')
        print('=' * 60)
        print(f'Total productos en BD: {Producto.query.count()}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reset', action='store_true', help='Borra TODA la data antes de importar')
    parser.add_argument('--yes', '-y', action='store_true', help='No pedir confirmacion')
    args = parser.parse_args()

    main(reset=args.reset, skip_confirm=args.yes)