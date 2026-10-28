import os
import sys
import re
import unicodedata
import pandas as pd

try:
    from rapidfuzz import fuzz
except ImportError:
    print("ERROR: falta rapidfuzz. Instala con: .\\venv\\Scripts\\pip.exe install rapidfuzz")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_LOGGRO = os.path.join(BASE_DIR, 'data', 'loggro_items.xlsx')
RUTA_MAESTRO = os.path.join(BASE_DIR, 'data', 'Inventario_Maestro_Completo.xlsx')
RUTA_SALIDA = os.path.join(BASE_DIR, 'data', 'Revision_Codigos.xlsx')

PREFIJOS_QUITAR = re.compile(r'^(UN\.|B\.|D\.|T\.|C\.|R\.|U\.|P\.)\s*', re.IGNORECASE)

def quitar_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def normalizar(texto):
    if pd.isna(texto):
        return ""
    texto = str(texto).strip().upper()
    texto = quitar_acentos(texto)
    texto = PREFIJOS_QUITAR.sub('', texto)
    texto = texto.replace('DX', ' X ')
    texto = texto.replace('PX', ' X ')
    texto = texto.replace('BX', ' X ')
    texto = texto.replace('UX', ' ')
    texto = re.sub(r'[^A-Z0-9\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def extraer_tamano(texto):
    texto = texto.upper()
    patrones = re.findall(
        r'(\d+(?:[.,]\d+)?)\s*(U|UN|UND|UNI|G|GR|GRS|ML|L|CC|KG|LIB|LB)\b',
        texto
    )
    tamanos = set()
    for num, unidad in patrones:
        num = num.replace(',', '.')
        if unidad in ('U', 'UN', 'UND', 'UNI'):
            u = 'U'
        elif unidad in ('G', 'GR', 'GRS'):
            u = 'G'
        elif unidad in ('ML', 'CC'):
            u = 'ML'
        elif unidad == 'L':
            u = 'L'
        elif unidad == 'KG':
            u = 'KG'
        elif unidad in ('LIB', 'LB'):
            u = 'LB'
        else:
            u = unidad
        tamanos.add(f"{num}{u}")
    return tamanos

def calcular_score(nombre_michin, nombre_loggro):
    n1 = normalizar(nombre_michin)
    n2 = normalizar(nombre_loggro)
    if not n1 or not n2:
        return 0.0

    nombre_score = fuzz.WRatio(n1, n2) / 100.0

    t1 = extraer_tamano(n1)
    t2 = extraer_tamano(n2)
    if t1 and t2:
        tam_score = 1.0 if (t1 & t2) else 0.0
    else:
        tam_score = 0.5

    score = (nombre_score * 0.7) + (tam_score * 0.3)
    return round(score * 100, 1)

def clasificar(score):
    if score >= 85:
        return "ALTA"
    if score >= 70:
        return "MEDIA"
    return "BAJA"

def sugerir():
    print("--- SUGERENCIAS v2 (RAPIDFUZZ + TAMANO) ---")

    if not os.path.exists(RUTA_LOGGRO):
        print(f"ERROR: falta {RUTA_LOGGRO}")
        return
    if not os.path.exists(RUTA_MAESTRO):
        print(f"ERROR: falta {RUTA_MAESTRO}")
        return

    df_loggro = pd.read_excel(RUTA_LOGGRO)
    df_maestro = pd.read_excel(RUTA_MAESTRO)

    loggro_lista = []
    for _, row in df_loggro.iterrows():
        nombre = row.get('Descripción')
        codigo = row.get('Ítem')
        if pd.isna(nombre) or pd.isna(codigo):
            continue
        codigo = str(codigo).strip()
        if codigo.startswith("(01)"):
            codigo = codigo[4:]
        if not codigo or codigo in ('nan', 'None'):
            continue
        loggro_lista.append({'nombre': str(nombre), 'codigo': codigo})

    print(f"Items Loggro validos: {len(loggro_lista)}")

    resultados = []
    for _, row in df_maestro.iterrows():
        prod_id = row.get('ID (NO TOCAR)')
        if pd.isna(prod_id):
            continue

        nombre_michin = row.get('Nombre Producto')
        codigo_actual = row.get('Código Barras')
        cs = str(codigo_actual).strip() if pd.notna(codigo_actual) else ""

        # Solo procesar si el codigo esta vacio o corrupto (tiene letras)
        es_corrupto = (not cs) or (not cs.isdigit())
        if not es_corrupto:
            continue

        mejor = None
        mejor_score = 0.0
        for item in loggro_lista:
            score = calcular_score(nombre_michin, item['nombre'])
            if score > mejor_score:
                mejor_score = score
                mejor = item

        if mejor is None or mejor_score < 50:
            continue

        resultados.append({
            'ID': prod_id,
            'Nombre Michin': nombre_michin,
            'Codigo Actual': cs,
            'Nombre Loggro': mejor['nombre'],
            'Codigo Sugerido': mejor['codigo'],
            'Score': mejor_score,
            'Confianza': clasificar(mejor_score),
            'Aplicar (S/N)': '',
        })

    if not resultados:
        print("No se generaron sugerencias.")
        return

    df_res = pd.DataFrame(resultados)
    df_res = df_res.sort_values(by='Score', ascending=False)

    altas = int((df_res['Confianza'] == 'ALTA').sum())
    medias = int((df_res['Confianza'] == 'MEDIA').sum())
    bajas = int((df_res['Confianza'] == 'BAJA').sum())

    df_res.to_excel(RUTA_SALIDA, index=False)

    print(f"\n--- TERMINADO ---")
    print(f"Total con sugerencia: {len(df_res)}")
    print(f"  ALTA  (>=85%, auto)     : {altas}")
    print(f"  MEDIA (70-85%, revisar) : {medias}")
    print(f"  BAJA  (<70%, no se usa) : {bajas}")
    print(f"Archivo: {RUTA_SALIDA}")
    print(f"\nSIGUIENTE PASO: abre el Excel y revisa las filas MEDIA.")

if __name__ == '__main__':
    sugerir()