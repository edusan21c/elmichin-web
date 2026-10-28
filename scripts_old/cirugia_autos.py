import sys
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from app.models.producto import Producto
from sqlalchemy import text

app = create_app()
with app.app_context():
    autos = Producto.query.filter(Producto.codigo_barras.like('AUTO-%')).all()
    print(f"--- INICIANDO CIRUGIA INTELIGENTE PARA {len(autos)} FANTASMAS ---")
    
    borrados = 0
    fallidos = 0
    
    for ghost in autos:
        # Tomamos las primeras 12 letras del nombre para buscar coincidencias
        prefijo = ghost.nombre[:12].strip()
        
        # Buscamos productos parecidos que NO sean AUTO-
        posibles = Producto.query.filter(
            Producto.nombre.ilike(f'%{prefijo}%'),
            ~Producto.codigo_barras.like('AUTO-%')
        ).all()
        
        # Si encontramos EXACTAMENTE 1 producto parecido, es una coincidencia segura
        if len(posibles) == 1:
            real = posibles[0]
            # 1. Mover renglones de factura
            db.session.execute(text(f"UPDATE detalle_factura SET producto_id = {real.id} WHERE producto_id = {ghost.id}"))
            # 2. Mover ventas
            db.session.execute(text(f"UPDATE ventas SET producto_id = {real.id} WHERE producto_id = {ghost.id}"))
            # 3. Borrar stock viejo
            db.session.execute(text(f"DELETE FROM producto_tienda WHERE producto_id = {ghost.id}"))
            # 4. Borrar el fantasma
            db.session.delete(ghost)
            print(f"OK: Se unio '{ghost.nombre}' -> '{real.nombre}'")
            borrados += 1
        elif len(posibles) > 1:
            print(f"ATENCION: '{ghost.nombre}' tiene varias coincidencias. Se deja oculto.")
            fallidos += 1
        else:
            print(f"ATENCION: No se encontro ningun producto parecido a '{ghost.nombre}'. Se deja oculto.")
            fallidos += 1
            
    db.session.commit()
    print(f"\n--- TERMINADO ---")
    print(f"Productos borrados y unidos exitosamente: {borrados}")
    print(f"Productos que requieren revision manual: {fallidos}")