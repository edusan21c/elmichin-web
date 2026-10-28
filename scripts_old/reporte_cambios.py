import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_MAESTRO = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Completo.xlsx')
RUTA_FINAL = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Final.xlsx')
RUTA_SALIDA = os.path.join(BASE_DIR, 'data', 'Reporte_Cambios_Codigos.xlsx')

def generar_reporte():
    print("--- GENERANDO REPORTE DE CAMBIOS ---")

    if not os.path.exists(RUTA_MAESTRO) or not os.path.exists(RUTA_FINAL):
        print("ERROR: Faltan los archivos Excel.")
        return

    # Leemos ambos Excel asegurando que los códigos sean texto
    df_antes = pd.read_excel(RUTA_MAESTRO, dtype={'Código Barras': str, 'ID (NO TOCAR)': str})
    df_despues = pd.read_excel(RUTA_FINAL, dtype={'Código Barras': str, 'ID (NO TOCAR)': str})

    cambios = []

    # Cruzamos la información por el ID del producto
    for idx, row_antes in df_antes.iterrows():
        pid = str(row_antes.get('ID (NO TOCAR)')).strip()
        if pd.isna(pid) or pid == 'None':
            continue

        # Buscamos el mismo producto en el archivo final
        match = df_despues[df_despues['ID (NO TOCAR)'] == pid]
        
        if not match.empty:
            row_despues = match.iloc[0]
            
            cod_antes = str(row_antes.get('Código Barras')).strip()
            cod_despues = str(row_despues.get('Código Barras')).strip()

            # Si el código cambió, lo guardamos en el reporte
            if cod_antes != cod_despues:
                # Clasificamos el cambio
                if cod_despues.startswith('200'):
                    tipo = "Interno (Generado)"
                else:
                    tipo = "Real (De Loggro)"

                cambios.append({
                    'ID': pid,
                    'Producto': row_antes.get('Nombre Producto'),
                    'Categoría': row_antes.get('Categoría'),
                    'Código Antes (Error)': cod_antes,
                    'Código Nuevo (Limpio)': cod_despues,
                    'Tipo de Código': tipo
                })

    if not cambios:
        print("No hubo cambios (los archivos son idénticos).")
        return

    df_reporte = pd.DataFrame(cambios)
    df_reporte.to_excel(RUTA_SALIDA, index=False)

    # Contamos cuántos de cada uno
    reales = len(df_reporte[df_reporte['Tipo de Código'] == 'Real (De Loggro)'])
    internos = len(df_reporte[df_reporte['Tipo de Código'] == 'Interno (Generado)'])

    print(f"\n--- REPORTE TERMINADO ---")
    print(f"Total de productos modificados: {len(df_reporte)}")
    print(f"  -> Códigos reales recuperados de Loggro: {reales}")
    print(f"  -> Códigos internos generados (200...): {internos}")
    print(f"\nArchivo generado: {RUTA_SALIDA}")

if __name__ == '__main__':
    generar_reporte()