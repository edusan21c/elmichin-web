import sys
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from app.models.producto import Producto

app = create_app()
with app.app_context():
    # Buscamos los 58 fantasmas
    autos = Producto.query.filter(Producto.codigo_barras.like('AUTO-%')).all()
    contador = 0
    
    for p in autos:
        # Los pasamos a INACTIVO sin tocarlos del todo
        p.categoria = 'INACTIVO'
        contador += 1
        
    db.session.commit()
    print(f"\n--- PROCESO TERMINADO ---")
    print(f"Se ocultaron exitosamente {contador} productos fantasmas (AUTO-).")