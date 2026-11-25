from app import create_app
from app.models.producto import Producto
app = create_app()
app.app_context().push()

activos = Producto.query.filter(Producto.categoria != 'INACTIVO').order_by(Producto.codigo_barras).all()
with open('C:\\michin_web\\central_activos.txt', 'w', encoding='utf-8') as f:
    for p in activos:
        f.write(f"{p.codigo_barras}|{p.nombre}\n")
print(f"¡Listo! {len(activos)} productos activos exportados de la Central.")
