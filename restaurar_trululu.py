from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

trucos = {
    'Caramelo Salado': 'B. Trululu Caramelo Salado 100g 54g',
    'Helado Fresa': 'B. Trululu Helado Fresa 100g 54g',
    'Volcan': 'B. Trululu Volcan Chocolate 100g 54g',
    'Unicornio': 'B. Trululu Unicornio 100g 43g',
    'Choco Banana': 'B. Trululu Masmelos Choco Banana 100g 50g'
}

print("Restaurando nombres de la familia Trululu en la Central...")

for key, new_name in trucos.items():
    p = Producto.query.filter(Producto.nombre.ilike(f'%{key}%')).first()
    if p:
        p.nombre = new_name
        p.categoria = 'dulces'
        ProductoTienda.query.filter_by(producto_id=p.id).update({'sync_estado': 'pendiente'})
        print(f"  Corregido: {new_name}")
    else:
        print(f"  No encontrado: {key}")

db.session.commit()
print("¡Listo! Nombres restaurados en la Central.")
