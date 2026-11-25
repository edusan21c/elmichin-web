from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

# 1. Contamos todos los registros que la Central tiene para la Tienda 2
total_asignado_t2 = ProductoTienda.query.filter_by(tienda_id=2).count()

# 2. Contamos solo los que están ACTIVOS (que no sean INACTIVO)
activos_t2 = db.session.query(ProductoTienda).join(Producto).filter(
    ProductoTienda.tienda_id == 2,
    Producto.categoria != 'INACTIVO'
).count()

print("=========================================")
print(f"  TIENDA 2 (Según la Central)")
print(f"  Total de registros: {total_asignado_t2}")
print(f"  ✅ PRODUCTOS ACTIVOS: {activos_t2}")
print("=========================================")
