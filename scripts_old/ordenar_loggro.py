import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_LOGGRO = os.path.join(BASE_DIR, 'data', 'loggro_items.xlsx')
RUTA_SALIDA = os.path.join(BASE_DIR, 'data', 'Loggro_Ordenado.xlsx')

def ordenar():
    print("--- ORDENANDO EL ARCHIVO DE LOGGRO ALFABETICAMENTE ---")

    if not os.path.exists(RUTA_LOGGRO):
        print("ERROR: No se encontró el archivo loggro_items.xlsx en la carpeta data.")
        return

    # 1. Leer el archivo original
    df = pd.read_excel(RUTA_LOGGRO)

    # 2. Ordenar por la columna 'Descripción' (de la A a la Z)
    # El na_position='last' pone los que estén vacíos al final de todo
    df_ordenado = df.sort_values(by='Descripción', ascending=True, na_position='last')

    # 3. Guardar el archivo nuevo
    df_ordenado.to_excel(RUTA_SALIDA, index=False)
    
    print(f"\n--- TERMINADO ---")
    print(f"El archivo ha sido ordenado y guardado en:")
    print(f"{RUTA_SALIDA}")
    print("Nota: Se han conservado todas las columnas originales (Precios, IVA, etc.).")

if __name__ == '__main__':
    ordenar()