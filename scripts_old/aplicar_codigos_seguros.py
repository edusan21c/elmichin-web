import os
import sys
import pandas as pd
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

RUTA_MAESTRO = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Completo.xlsx')
RUTA_SUGERENCIAS = os.path.join(BASE_DIR, 'data', 'Sugerencias_Codigos.xlsx')
RUTA_SALIDA = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Seguro.xlsx')

def aplicar_codigos():
    print("--- APLICANDO CODIGOS SEGUROS (SIMILITUD >= 90%) ---")
    
    if not os.path.exists(RUTA_MAESTRO) or not os.path.exists(RUTA_SUGERENCIAS):
        print("ERROR: Faltan archivos.")
        return

    # 1. Cargar sugerencias y filtrar solo las muy seguras
    df_sug = pd.read_excel(RUTA_SUGERENCIAS)
    df_sug_seguras = df_sug[df_sug['Similitud (%)'] >= 90.0]
    
    # Crear diccionario: ID -> Codigo Sugerido
    dicc_sugerencias = dict(zip(df_sug_seguras['ID (NO TOCAR)'], df_sug_seguras['Código Sugerido']))

    print(f"Sugerencias con 90% o mas de seguridad: {len(dicc_sugerencias)}")

    # 2. Cargar el maestro
    df_maestro = pd.read_excel(RUTA_MAESTRO)
    actualizados = 0

    # 3. Iterar y actualizar SOLO la columna del codigo
    for idx, row in df_maestro.iterrows():
        prod_id = row.get('ID (NO TOCAR)')
        
        if pd.notna(prod_id) and prod_id in dicc_sugerencias:
            codigo_actual = str(row.get('Código Barras'))
            
            # Solo actualizamos si el codigo actual esta vacio o tiene letras
            if not codigo_actual.isdigit() or pd.isna(row.get('Código Barras')):
                df_maestro.at[idx, 'Código Barras'] = dicc_sugerencias[prod_id]
                actualizados += 1

    # 4. Guardar en un archivo NUEVO
    df_maestro.to_excel(RUTA_SALIDA, index=False)
    
    print(f"\n--- TERMINADO ---")
    print(f"Codigos actualizados (solo columnas de codigo): {actualizados}")
    print(f"Archivo guardado como: {RUTA_SALIDA}")

if __name__ == '__main__':
    aplicar_codigos()