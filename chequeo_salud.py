from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.factura import DetalleFactura
from sqlalchemy import func

app = create_app()
app.app_context().push()

print("==================================================")
print("        CHEQUEO DE SALUD DE LA BASE DE DATOS       ")
print("==================================================")

# 1. Productos huérfanos (Stock en tienda que apunta a un producto que ya no existe)
huerfanos = db.session.query(ProductoTienda).outerjoin(Producto).filter(Producto.id == None).count()
print(f"1. Stock huérfano (sin producto): {huerfanos} registros")

# 2. Stock Negativo (Nadie debería tener menos de 0)
negativos = ProductoTienda.query.filter(ProductoTienda.cantidad < 0).count()
print(f"2. Productos con stock NEGATIVO: {negativos} registros")

# 3. Códigos de barras duplicados (excluyendo los vacíos)
duplicados_cod = db.session.query(Producto.codigo_barras, func.count(Producto.id)).filter(Producto.codigo_barras != None, Producto.codigo_barras != '').group_by(Producto.codigo_barras).having(func.count(Producto.id) > 1).all()
print(f"3. Códigos de barras duplicados: {len(duplicados_cod)} casos")
for cod, cant in duplicados_cod:
    print(f"   - Código {cod} está repetido {cant} veces")

# 4. Nombres duplicados en productos ACTIVOS
duplicados_nombre = db.session.query(Producto.nombre, func.count(Producto.id)).filter(func.coalesce(Producto.categoria, '') != 'INACTIVO').group_by(Producto.nombre).having(func.count(Producto.id) > 1).all()
print(f"4. Nombres de productos ACTIVOS duplicados: {len(duplicados_nombre)} casos")
for nom, cant in duplicados_nombre:
    print(f"   - '{nom}' está repetido {cant} veces")

# 5. Productos sin código de barras (activos)
sin_codigo = Producto.query.filter(func.coalesce(Producto.categoria, '') != 'INACTIVO', (Producto.codigo_barras == None) | (Producto.codigo_barras == '')).count()
print(f"5. Productos ACTIVOS sin código de barras: {sin_codigo} registros")

# 6. Facturas que apuntan a productos borrados (Peligro de romper historial)
facturas_huerfanas = db.session.query(DetalleFactura).outerjoin(Producto).filter(Producto.id == None).count()
print(f"6. Ventas (facturas) apuntando a productos inexistentes: {facturas_huerfanas} registros")

# 7. Estado de Sincronización
pendientes = ProductoTienda.query.filter_by(sync_estado='pendiente').count()
print(f"7. Registros pendientes por sincronizar: {pendientes}")

print("==================================================")
print("FIN DEL CHEQUEO")
