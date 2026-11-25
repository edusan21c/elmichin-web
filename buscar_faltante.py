from app import create_app
from app.models.producto import Producto

app = create_app()
app.app_context().push()

# Obtenemos todos los productos activos de la Central
activos_central = Producto.query.filter(Producto.categoria != 'INACTIVO').all()

print("Buscando el producto que falta en la Tienda 1...")
# Nota: Como no tenemos acceso a la base de la Tienda 1 desde aquí, 
# buscaremos el último producto modificado que podría no haber llegado.
ultimo = Producto.query.order_by(Producto.actualizado_en.desc()).first()

if ultimo:
    print(f"El último producto modificado en la Central es:")
    print(f"ID: {ultimo.id} | Nombre: '{ultimo.nombre}' | Cat: {ultimo.categoria}")
    print("Si este es el producto que falta, en 1 minuto el Worker de la Tienda 1 lo bajará y el contador subirá a 1459.")
