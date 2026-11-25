from app import create_app
from app.models.producto import Producto
from app.extensions import db

app = create_app()
app.app_context().push()

productos = Producto.query.all()
with open('C:\\michin_web\\central_inventario.txt', 'w', encoding='utf-8') as f:
    for p in productos:
        f.write(f"{p.id}|{p.codigo_barras}|{p.nombre}|{p.categoria}\n")

print(f"¡Listo! Se exportaron {len(productos)} productos de la Central al archivo central_inventario.txt")
