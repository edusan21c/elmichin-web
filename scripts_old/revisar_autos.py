import sys
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from app.models.producto import Producto

app = create_app()
with app.app_context():
    autos = Producto.query.filter(Producto.codigo_barras.like('AUTO-%')).all()
    print(f"\n--- LISTA DE LOS {len(autos)} PRODUCTOS FANTASMAS ---")
    for p in autos:
        print(f"ID: {p.id} | Nombre: {p.nombre}")