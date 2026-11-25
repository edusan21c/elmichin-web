from app import create_app
from app.models.producto import Producto
from app.extensions import db

app = create_app()
app.app_context().push()

# Buscamos todos los productos que empiecen con [GHOST]
fantasmas = Producto.query.filter(Producto.nombre.like('[GHOST]%')).all()

for p in fantasmas:
    p.categoria = 'INACTIVO'
    # Le quitamos el [GHOST] del nombre para que quede limpio en el historial
    p.nombre = p.nombre.replace('[GHOST] ', '').strip()

db.session.commit()
print(f"Se inactivaron y limpiaron {len(fantasmas)} productos fantasma.")
