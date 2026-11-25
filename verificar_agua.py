from app import create_app
from app.models.producto import Producto
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- VERIFICANDO SI LA CENTRAL TIENE EL AGUA CIELO CHUPO ---")
# Buscamos el producto por el nombre
p = Producto.query.filter(Producto.nombre.ilike('%Agua Cielo 1000mL Chupo%')).first()
if p:
    print(f"SÍ EXISTE en Central. ID: {p.id} | Nombre: '{p.nombre}' | Código: {p.codigo_barras} | Cat: {p.categoria}")
else:
    print("NO EXISTE en Central.")
