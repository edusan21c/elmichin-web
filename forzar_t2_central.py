from app import create_app
from app.models.producto import ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

registros = ProductoTienda.query.filter_by(tienda_id=2).update({'sync_estado': 'pendiente'})
db.session.commit()
print(f"Se marcaron {registros} registros de la Tienda 2 como pendientes en la Central.")
