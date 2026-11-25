from app import create_app
from app.models.producto import Producto

app = create_app()
app.app_context().push()

total = Producto.query.count()
# Contamos los que NO están en INACTIVO
activos = Producto.query.filter(Producto.categoria != 'INACTIVO').count()
inactivos = total - activos

print("=========================================")
print(f"  TOTAL EN LA BASE DE DATOS: {total}")
print(f"  ✅ PRODUCTOS ACTIVOS:      {activos}")
print(f"  🛑 PRODUCTOS INACTIVOS:    {inactivos}")
print("=========================================")
