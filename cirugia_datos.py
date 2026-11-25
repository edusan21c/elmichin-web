from app import create_app
from app.models.producto import Producto, ProductoTienda
from app.extensions import db

app = create_app()
app.app_context().push()

print("--- INICIANDO CIRUGÍA DE DATOS EN LA CENTRAL ---")

# 1. ARREGLAR EL CHOQUE DE CÓDIGOS DEL UNICORNIO
# El Trululu Unicornio en la Central tiene el código falso 'cda50...' que choca con el Candy Toy.
# Vamos a devolverle su código real.
p_unicornio = Producto.query.filter(Producto.nombre.ilike('%Trululu Unicornio%')).first()
if p_unicornio:
    p_unicornio.codigo_barras = '7702993056745'  # Código real del Unicornio
    p_unicornio.nombre = 'B. Trululu Unicornio 100g 43g' # Nombre con el truco
    p_unicornio.categoria = 'dulces'
    print("  Unicornio corregido con su código real 7702993056745.")

# Si hay otro producto en Central con ese código 7702993056745, lo aislamos
p_conflicto = Producto.query.filter(Producto.codigo_barras == '7702993056745', Producto.id != p_unicornio.id).first()
if p_conflicto:
    p_conflicto.codigo_barras = 'BORRAR-DUPLICADO-UNICORNIO'
    p_conflicto.categoria = 'INACTIVO'
    print(f"  Producto en conflicto ({p_conflicto.nombre}) aislamiento.")

# 2. ARREGLAR EL NOMBRE DEL SHAMPOO H&S
p_hs = Producto.query.filter(Producto.nombre.ilike('%H&S%Rosado%')).first()
if p_hs:
    p_hs.nombre = 'Un. H&S (Hys) Shampoox12 Rosado'
    print("  Shampoo H&S renombrado y estandarizado.")

# 3. MARCAR EL L&M FALTANTE PARA ENVIARLO A LAS TIENDAS
p_lm = Producto.query.filter(Producto.nombre.ilike('%L&M Verde & Rojo 20u%')).first()
if p_lm:
    for t_id in [1, 2]:
        pt = ProductoTienda.query.filter_by(producto_id=p_lm.id, tienda_id=t_id).first()
        if pt:
            pt.sync_estado = 'pendiente'
    print("  L&M marcado para enviar a las tiendas.")

# 4. FORZAR LA SINCRONIZACIÓN DE TODOS LOS PRODUCTOS QUE ARREGLAMOS
for p in [p_unicornio, p_hs, p_lm]:
    if p:
        for t_id in [1, 2]:
            pt = ProductoTienda.query.filter_by(producto_id=p.id, tienda_id=t_id).first()
            if pt:
                pt.sync_estado = 'pendiente'

db.session.commit()
print("¡Cirugía terminada! Los datos están listos para enviarse a la nube y a las tiendas.")
