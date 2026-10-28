import os
import sys
import pandas as pd
import difflib
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

RUTA_LOGGRO = os.path.join(BASE_DIR, 'data', 'loggro_items.xlsx')
RUTA_MAESTRO = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Completo.xlsx')
RUTA_SALIDA = os.path.join(BASE_DIR, 'data', 'Sugerencias_Codigos.xlsx')

def limpiar_nombre(texto):
    if pd.isna(texto): return ""
    texto = str(texto).strip().upper()
    # Quitar prefijos comunes de El Michin
    texto = re.sub(r'^(UN\.|B\.|D\.|T\.|C\.|R\.|U\.|P\.)\s*', '', texto)
    # Quitar signos y dejar solo letras y numeros
    texto = re.sub(r'[^A-Z0-9\s]', '', texto)
    return texto.strip()

def sugerir():
    print("--- GENERANDO SUGERENCIAS INTELIGENTES DE CODIGOS ---")
    
    if not os.path.exists(RUTA_LOGGRO) or not os.path.exists(RUTA_MAESTRO):
        print("ERROR: Falta uno de los archivos en la carpeta data.")
        return

    df_loggro = pd.read_excel(RUTA_LOGGRO)
    df_maestro = pd.read_excel(RUTA_MAESTRO)

    # Preparamos la lista de Loggro
    loggro_limpio = []
    for _, row in df_loggro.iterrows():
        nombre_orig = str(row.get('Descripción'))
        nombre_limpio = limpiar_nombre(nombre_orig)
        codigo = str(row.get('Ítem')).strip()
        
        if codigo.startswith("(01)"):
            codigo = codigo[4:]
            
        loggro_limpio.append({
            'nombre_limpio': nombre_limpio,
            'nombre_original_loggro': nombre_orig,
            'codigo': codigo
        })

    resultados = []

    for idx, row in df_maestro.iterrows():
        nombre_maestro = str(row.get('Nombre Producto'))
        nombre_m_limpio = limpiar_nombre(nombre_maestro)
        
        # Buscar las mejores coincidencias
        opciones = [l['nombre_limpio'] for l in loggro_limpio]
        mejores = difflib.get_close_matches(nombre_m_limpio, opciones, n=1, cutoff=0.6) # 60% de similitud

        if mejores:
            mejor_match = mejores[0]
            # Encontrar los datos originales de esa mejor coincidencia
            for l in loggro_limpio:
                if l['nombre_limpio'] == mejor_match:
                    # Calcular el porcentaje de similitud
                    ratio = difflib.SequenceMatcher(None, nombre_m_limpio, mejor_match).ratio() * 100
                    
                    resultados.append({
                        'ID (NO TOCAR)': row.get('ID (NO TOCAR)'),
                        'Nombre en El Michín': nombre_maestro,
                        'Nombre en Loggro (Sugerencia)': l['nombre_original_loggro'],
                        'Código Sugerido': l['codigo'],
                        'Similitud (%)': round(ratio, 1)
                    })
                    break

    df_resultados = pd.DataFrame(resultados)
    df_resultados = df_resultados.sort_values(by='Similitud (%)', ascending=False)
    
    df_resultados.to_excel(RUTA_SALIDA, index=False)
    
    print(f"\n--- TERMINADO ---")
    print(f"Se generaron {len(df_resultados)} sugerencias.")
    print(f"Revisa el archivo: {RUTA_SALIDA}")
    print("Filtra por 'Similitud (%)' mayor a 80% para aceptar las que casi seguro son correctas.")

if __name__ == '__main__':
    sugerir()