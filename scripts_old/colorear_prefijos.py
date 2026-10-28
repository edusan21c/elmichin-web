import os
import re
import openpyxl
from openpyxl.styles import PatternFill

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_ENTRADA = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Final.xlsx')
RUTA_SALIDA = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Coloreado.xlsx')

def limpiar_y_colorear():
    print("--- QUITANDO PREFIJOS Y APLICANDO COLORES ---")

    if not os.path.exists(RUTA_ENTRADA):
        print(f"ERROR: No se encontró {RUTA_ENTRADA}")
        return

    wb = openpyxl.load_workbook(RUTA_ENTRADA)
    ws = wb.active

    headers = [cell.value for cell in ws[1]]
    col_nombre_idx = headers.index('Nombre Producto') + 1

    # Diccionario: (Patrón de búsqueda, Color de relleno)
    reglas = [
        (re.compile(r'^(Un\.|U\.)\s*', re.IGNORECASE), PatternFill(start_color='ADD8E6', end_color='ADD8E6', fill_type='solid')), # Azul (Unidades)
        (re.compile(r'^(B\.)\s*', re.IGNORECASE), PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')),      # Verde (Bolsas)
        (re.compile(r'^(D\.)\s*', re.IGNORECASE), PatternFill(start_color='FFB6C1', end_color='FFB6C1', fill_type='solid')),      # Rosado (Displays)
        (re.compile(r'^(Ag\.)\s*', re.IGNORECASE), PatternFill(start_color='FFDAB9', end_color='FFDAB9', fill_type='solid')),     # Naranja (Aguardientes)
        (re.compile(r'^(T\.)\s*', re.IGNORECASE), PatternFill(start_color='E6E6FA', end_color='E6E6FA', fill_type='solid')),      # Morado (Tarros)
        (re.compile(r'^(C\.)\s*', re.IGNORECASE), PatternFill(start_color='FFFFE0', end_color='FFFFE0', fill_type='solid')),      # Amarillo (Cajas)
        (re.compile(r'^(R\.)\s*', re.IGNORECASE), PatternFill(start_color='F08080', end_color='F08080', fill_type='solid')),      # Rojo suave (Ristras)
        (re.compile(r'^(P\.)\s*', re.IGNORECASE), PatternFill(start_color='D3D3D3', end_color='D3D3D3', fill_type='solid')),      # Gris (Paquetes)
    ]

    limpiados = 0
    coloreados = 0

    for row in range(2, ws.max_row + 1):
        cell = ws.cell(row=row, column=col_nombre_idx)
        if not cell.value:
            continue
            
        nombre_original = str(cell.value).strip()
        nombre_limpio = nombre_original

        # Buscar qué prefijo tiene y limpiarlo
        for patron, color in reglas:
            if patron.search(nombre_limpio):
                # Quita el prefijo del texto
                nombre_limpio = patron.sub('', nombre_limpio).strip()
                # Pinta la celda del color correspondiente
                cell.fill = color
                coloreados += 1
                break # Una vez encuentra el prefijo, deja de buscar

        # Si el nombre cambió, actualizamos la celda
        if nombre_limpio != nombre_original:
            cell.value = nombre_limpio
            limpiados += 1

    wb.save(RUTA_SALIDA)
    print(f"\n--- TERMINADO ---")
    print(f"Nombres limpios (sin prefijos): {limpiados}")
    print(f"Celdas coloreadas: {coloreados}")
    print(f"Archivo guardado como: {RUTA_SALIDA}")

if __name__ == '__main__':
    limpiar_y_colorear()