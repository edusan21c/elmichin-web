from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# Buscamos los productos que tienen ventas, precio 0 y stock 0 (los fantasmas)
productos = Producto.query.filter(Producto.categoria == 'INACTIVO').all()
ids_fantasmas = []

for p in productos:
    # Verificamos si estaba en la lista de los 9 (agua cielo, chocoramo, etc.)
    if p.nombre in [
        'Un. Agua Cielo 1000mL Chupo', 'B. Chocoramo 5u', 'D. Bianchi Bar Xl X12 Maní & Caramelo (Naranja)',
        'Un. Lucky Strike Sandia 10u', 'Un. Rothmans Gris 10u', 'D. Encendedor El Reyx20Un.',
        'B. Chupeta Corazonzitos Colombianox50', 'Un. Gran Big Ben (Bx100)', 'Un. Ponky X 8U Nucita'
    ]:
        ids_fantasmas.append(p.id)

# Los marcamos como pendientes en las tiendas
if ids_fantasmas:
    cantidad = ProductoTienda.query.filter(ProductoTienda.producto_id.in_(ids_fantasmas)).update({'sync_estado': 'pendiente'}, synchronize_session=False)
    db.session.commit()
    print(f"¡Listo! Se marcaron {cantidad} registros de fantasmas como pendientes.")
else:
    print("No se encontraron los fantasmas para marcar.")
