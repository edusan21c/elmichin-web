from app import create_app
from app.models.producto import ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# Marcamos TODO el catálogo de la Tienda 1 como pendiente para subirlo
cantidad = ProductoTienda.query.update({'sync_estado': 'pendiente'})
db.session.commit()
print(f"¡Listo! Se marcaron {cantidad} productos para enviar a la nube.")
