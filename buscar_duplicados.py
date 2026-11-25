from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from app.extensions import db
from sqlalchemy import func

app = create_app()
app.app_context().push()

print("=========================================================")
print("   BUSCANDO NOMBRES DUPLICADOS EN TODO EL SISTEMA")
print("=========================================================")

# Agrupamos por nombre y contamos cuántas veces se repite
duplicados = db.session.query(
    Producto.nombre, 
    func.count(Producto.id).label('cantidad')
).group_by(Producto.nombre).having(func.count(Producto.id) > 1).all()

if not duplicados:
    print("¡Excelente! No se encontraron nombres duplicados.")
else:
    print(f"Se encontraron {len(duplicados)} nombres duplicados. Revisando detalles:\n")
    
    for nombre, cant in duplicados:
        print(f"🔴 NOMBRE REPETIDO: '{nombre}' (Aparece {cant} veces)")
        
        # Buscamos todos los productos con ese nombre
        productos = Producto.query.filter_by(nombre=nombre).all()
        
        for p in productos:
            pt_t1 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=1).first()
            pt_t2 = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=2).first()
            stock1 = pt_t1.cantidad if pt_t1 else 0
            stock2 = pt_t2.cantidad if pt_t2 else 0
            tiene_ventas = DetalleFactura.query.filter_by(producto_id=p.id).first() is not None
            
            print(f"   -> ID: {p.id} | Cat: {p.categoria} | T1 Stock: {stock1} | T2 Stock: {stock2} | ¿Tiene ventas?: {tiene_ventas}")
        print("-" * 50)

print("\nFIN DEL ANALISIS.")
