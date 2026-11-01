import sys
import os

# Esto le dice a Python que busque la carpeta 'app' en la raíz de michin_web
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import create_app
from app.models.producto import Producto, ProductoTienda
from datetime import datetime
import json

app = create_app()
app.app_context().push()

fecha = datetime.now().strftime('%Y%m%d_%H%M')
nombre_archivo = f"backup_inventario_{fecha}.json"

data = {
    'productos': [{'id': p.id, 'nombre': p.nombre, 'codigo': p.codigo_barras} for p in Producto.query.all()],
    'inventario': [{'prod_id': pt.producto_id, 'tienda_id': pt.tienda_id, 'cantidad': pt.cantidad} for pt in ProductoTienda.query.all()]
}

with open(nombre_archivo, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"✅ Respaldo creado con éxito en: {os.path.abspath(nombre_archivo)}")