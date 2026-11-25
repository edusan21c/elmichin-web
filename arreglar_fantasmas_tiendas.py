from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# Buscamos los fantasmas por sus nombres exactos
nombres_fantasmas = [
    'Un. Agua Cielo 1000mL Chupo', 'B. Chocoramo 5u', 
    'D. Bianchi Bar Xl X12 Maní & Caramelo (Naranja)',
    'Un. Lucky Strike Sandia 10u', 'Un. Rothmans Gris 10u', 
    'D. Encendedor El Reyx20Un.', 'B. Chupeta Corazonzitos Colombianox50', 
    'Un. Gran Big Ben (Bx100)', 'Un. Ponky X 8U Nucita'
]

productos = Producto.query.filter(Producto.nombre.in_(nombres_fantasmas)).all()
ids_fantasmas = [p.id for p in productos]

if ids_fantasmas:
    # Forzamos el estado a 'enviado_central' para que las tiendas lo vean
    cantidad = ProductoTienda.query.filter(ProductoTienda.producto_id.in_(ids_fantasmas)).update({'sync_estado': 'enviado_central'}, synchronize_session=False)
    db.session.commit()
    print(f"¡Listo! Se forzaron {cantidad} registros a 'enviado_central'. Las tiendas los bajarán solas en 1-2 minutos.")
else:
    print("No se encontraron los fantasmas.")
