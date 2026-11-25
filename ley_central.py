from app import create_app
from app.models.producto import ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("Preparando la 'Ley de la Central' para las tiendas...")

# 1. Marcamos TODOS los productos ACTIVOS de la Central como pendientes
# (Omitimos los inactivos para no saturar la nube con basura)
cantidad = ProductoTienda.query.filter(ProductoTienda.sync_estado != 'sincronizado').update({'sync_estado': 'pendiente'})
# También marcamos los que ya están sincronizados pero podrían necesitar un empujón (solo los de T1 y T2)
cantidad_t1 = ProductoTienda.query.filter_by(tienda_id=1).update({'sync_estado': 'pendiente'})
cantidad_t2 = ProductoTienda.query.filter_by(tienda_id=2).update({'sync_estado': 'pendiente'})

db.session.commit()
print(f"¡Listo! Se marcaron los productos de T1 y T2 para enviar.")
print("La Central va a enviar su catálogo. Esto puede tomar un par de minutos.")
