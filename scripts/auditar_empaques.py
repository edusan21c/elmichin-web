import os
import sys
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import create_app
from app.models.producto import Producto

app = create_app()
RUTA_REPORTE = os.path.join(BASE_DIR, 'data', 'reporte_empaques.txt')

def auditar():
    print("--- AUDITANDO CONTENEDORES (D. B. C. R.) Y UNIDADES ---")
    with app.app_context():
        productos = Producto.query.all()
        
        # Agrupamos por prefijo
        contenedores = [p for p in productos if p.nombre.upper().startswith(('D.', 'B.', 'C.', 'R.'))]
        unidades = [p for p in productos if p.nombre.upper().startswith(('UN.', 'U.', 'P.'))]

        with open(RUTA_REPORTE, 'w', encoding='utf-8') as f:
            f.write("=== ÁRBOL DE EMPAQUES VS UNIDADES ===\n\n")
            
            for c in contenedores:
                f.write(f"CONTENEDOR: {c.nombre} | Codigo: {c.codigo_barras}\n")
                
                # Intentar adivinar la unidad quitando el prefijo
                nombre_limpio = re.sub(r'^[A-Z]\.\s*', '', c.nombre, flags=re.IGNORECASE).strip().upper()
                
                # Buscar posibles "hijos" (unidades o bolsas más pequeñas)
                posibles_hijos = []
                for u in unidades:
                    nombre_u_limpio = re.sub(r'^[A-Z]\.\s*', '', u.nombre, flags=re.IGNORECASE).strip().upper()
                    # Si comparten gran parte del nombre
                    if nombre_limpio in nombre_u_limpio or nombre_u_limpio in nombre_limpio:
                        posibles_hijos.append(u)
                        
                if posibles_hijos:
                    for h in posibles_hijos:
                        f.write(f"   -> TIENE UNIDAD: {h.nombre} (Cod: {h.codigo_barras})\n")
                else:
                    f.write(f"   -> ⚠️ NO TIENE UNIDAD CREADA\n")
                f.write("\n")
                
    print(f"Reporte generado en: {RUTA_REPORTE}")
    os.startfile(RUTA_REPORTE)

if __name__ == '__main__':
    auditar()