import sys
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from app.models.producto import Producto
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Buscamos los IDs de los fantasmas
    autos = db.session.query(Producto.id, Producto.nombre).filter(Producto.codigo_barras.like('AUTO-%')).all()
    ids = [p.id for p in autos]
    
    if not ids:
        print("No se encontraron productos AUTO-")
    else:
        ids_str = ','.join(str(i) for i in ids)
        
        # Contamos cuántas ventas tienen
        ventas = db.session.execute(text(f"SELECT COUNT(*) FROM ventas WHERE producto_id IN ({ids_str})")).scalar()
        detalles = db.session.execute(text(f"SELECT COUNT(*) FROM detalle_factura WHERE producto_id IN ({ids_str})")).scalar()
        
        print(f"\n--- RESUMEN DE LOS {len(ids)} FANTASMAS ---")
        print(f"Ventas asociadas: {ventas}")
        print(f"Renglones de factura asociados: {detalles}")
        
        if ventas == 0 and detalles == 0:
            print("\nRESULTADO: Estan limpios. No tienen ventas. Se pueden borrar sin miedo.")
        else:
            print("\nRESULTADO: Tienen ventas. Si los borramos a la fuerza, la Caja perdera este dinero.")