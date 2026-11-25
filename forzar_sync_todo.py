from app import create_app
from app.models.producto import ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# Ponemos en 'pendiente' todos los productos de T1 y T2
registros = ProductoTienda.query.filter(ProductoTienda.tienda_id.in_([1, 2])).all()
for r in registros:
    r.sync_estado = 'pendiente'

db.session.commit()
print(f"¡Listo! Se marcaron {len(registros)} productos como 'pendiente' para re-enviar.")
