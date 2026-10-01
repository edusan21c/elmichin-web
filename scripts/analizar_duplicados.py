# scripts/analizar_duplicados.py
# Analiza los productos en la BD y detecta duplicados por similitud.
# SOLO LEE - NO modifica nada.
# Ejecutar: python scripts\analizar_duplicados.py

import os
import sys
import re
import unicodedata
from difflib import SequenceMatcher
from collections import defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.models.producto import Producto


def normalizar(nombre):
    """Normaliza un nombre: sin tildes, minúsculas, sin símbolos, espacios simples."""
    n = nombre.lower().strip()
    # Quitar tildes
    n = ''.join(c for c in unicodedata.normalize('NFD', n)
                if unicodedata.category(c) != 'Mn')
    # Reemplazar símbolos por espacio
    n = re.sub(r'[^\w\s]', ' ', n)
    # Espacios múltiples a uno
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def similitud(a, b):
    return SequenceMatcher(None, a, b).ratio()


def main():
    app = create_app()
    with app.app_context():
        productos = Producto.query.order_by(Producto.nombre).all()
        print(f'Total productos en BD: {len(productos)}')
        print()

        # Agrupar por nombre normalizado exacto
        grupos_exactos = defaultdict(list)
        for p in productos:
            grupos_exactos[normalizar(p.nombre)].append(p)

        duplicados_exactos = {k: v for k, v in grupos_exactos.items() if len(v) > 1}
        print(f'🔍 Duplicados EXACTOS (solo cambia tilde/mayúscula/símbolo): {len(duplicados_exactos)} grupos')
        print('-' * 80)

        for clave, grupo in list(duplicados_exactos.items())[:20]:
            print(f'  Clave: "{clave}"')
            for p in grupo:
                print(f'    - ID {p.id}: {p.nombre}')
        if len(duplicados_exactos) > 20:
            print(f'  ... y {len(duplicados_exactos) - 20} grupos más')
        print()

        # Duplicados por SIMILITUD alta (>= 0.90)
        print('🔍 Duplicados por SIMILITUD alta (>= 90%):')
        print('-' * 80)
        nombres_norm = [(p, normalizar(p.nombre)) for p in productos]
        vistos = set()
        grupos_similares = []

        for i, (p1, n1) in enumerate(nombres_norm):
            if p1.id in vistos:
                continue
            grupo = [p1]
            for p2, n2 in nombres_norm[i+1:]:
                if p2.id in vistos:
                    continue
                # Solo comparar si comparten al menos 3 caracteres al inicio
                if len(n1) < 3 or len(n2) < 3:
                    continue
                if similitud(n1, n2) >= 0.90:
                    grupo.append(p2)
                    vistos.add(p2.id)
            if len(grupo) > 1:
                vistos.add(p1.id)
                grupos_similares.append(grupo)

        for grupo in grupos_similares[:30]:
            print(f'  Grupo de {len(grupo)}:')
            for p in grupo:
                print(f'    - ID {p.id}: {p.nombre}')

        if len(grupos_similares) > 30:
            print(f'  ... y {len(grupos_similares) - 30} grupos más')

        print()
        print('=' * 80)
        print('RESUMEN:')
        print(f'  Total productos:              {len(productos)}')
        print(f'  Grupos con duplicados exactos: {len(duplicados_exactos)}')
        print(f'  Grupos con similitud >= 90%:   {len(grupos_similares)}')
        productos_en_duplicados = sum(len(g) for g in grupos_similares)
        productos_unicos = len(productos) - (productos_en_duplicados - len(grupos_similares))
        print(f'  Estimado después de limpieza:  ~{productos_unicos} productos únicos')
        print('=' * 80)
        print()
        print('⚠️  Este análisis NO modificó nada. Revisa el reporte y decide.')


if __name__ == '__main__':
    main()