from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from decimal import Decimal
import uuid
import random

def safe_dec(val):
    try:
        if val is None or str(val).strip() == '': return Decimal('0.00')
        return Decimal(str(val))
    except:
        return Decimal('0.00')

def safe_int(val):
    try:
        if val is None or str(val).strip() == '': return 0
        return int(val)
    except:
        return 0

@bp.route('/')
@login_required
def index():
    if not current_user.es_programador():
        return "Acceso denegado. Solo el programador puede ver esta página.", 403
    return render_template('inventario_pro/index.html')

@bp.route('/api/data')
@login_required
def get_data():
    productos = Producto.query.all()
    data = []
    for p in productos:
        t1 = p.get_presentacion(1)
        t2 = p.get_presentacion(2)
        
        fila = {
            'id': p.id,
            'nombre': p.nombre,
            'categoria': p.categoria or '',
            'codigo_barras': p.codigo_barras or '',
            't1_stock': t1.cantidad if t1 else 0,
            't1_costo': float(t1.precio_proveedor) if t1 else 0,
            't1_gan': float(t1.porcentaje) if t1 else 0,
            't1_base': float(t1.precio_venta) if t1 else 0,
            't1_c1': t1.condicion1 if t1 else '',
            't1_p1': float(t1.precio_venta1) if t1 else 0,
            't1_c2': t1.condicion2 if t1 else '',
            't1_p2': float(t1.precio_venta2) if t1 else 0,
            't2_stock': t2.cantidad if t2 else 0,
            't2_costo': float(t2.precio_proveedor) if t2 else 0,
            't2_gan': float(t2.porcentaje) if t2 else 0,
            't2_base': float(t2.precio_venta) if t2 else 0,
            't2_c1': t2.condicion1 if t2 else '',
            't2_p1': float(t2.precio_venta1) if t2 else 0,
            't2_c2': t2.condicion2 if t2 else '',
            't2_p2': float(t2.precio_venta2) if t2 else 0,
        }
        data.append(fila)
    return jsonify(data)

@bp.route('/api/save', methods=['POST'])
@login_required
def save_data():
    if not current_user.es_programador():
        return jsonify({"status": "error", "message": "No tienes permiso."}), 403
        
    cambios = request.json
    try:
        for fila in cambios:
            prod_id = fila.get('id')
            
            # FORZAMOS A ENTERO PARA QUE ACTUALICE BIEN
            if prod_id and str(prod_id).strip() != '':
                prod = Producto.query.get(int(prod_id))
            else:
                codigo_ingresado = fila.get('codigo_barras')
                if not codigo_ingresado:
                    while True:
                        nuevo_codigo = "200" + str(random.randint(100000000, 999999999))
                        if not Producto.query.filter_by(codigo_barras=nuevo_codigo).first():
                            codigo_ingresado = nuevo_codigo
                            break
                            
                prod = Producto(
                    nombre=fila.get('nombre'),
                    categoria=fila.get('categoria'),
                    codigo_barras=codigo_ingresado,
                    codigo_global=str(uuid.uuid4())
                )
                db.session.add(prod)
                db.session.flush()

            if not prod: continue
            
            # ACTUALIZAMOS EL NOMBRE Y DEMAS CAMPOS
            prod.nombre = fila.get('nombre')
            prod.categoria = fila.get('categoria')
            prod.codigo_barras = fila.get('codigo_barras') or None
            
            for t_id, prefix in [(1, 't1'), (2, 't2')]:
                pres = ProductoTienda.query.filter_by(producto_id=prod.id, tienda_id=t_id).first()
                if not pres:
                    pres = ProductoTienda(producto_id=prod.id, tienda_id=t_id)
                    db.session.add(pres)
                
                pres.cantidad = safe_int(fila.get(f'{prefix}_stock'))
                pres.precio_proveedor = safe_dec(fila.get(f'{prefix}_costo'))
                pres.porcentaje = safe_dec(fila.get(f'{prefix}_gan'))
                pres.precio_venta = safe_dec(fila.get(f'{prefix}_base'))
                pres.condicion1 = str(fila.get(f'{prefix}_c1', ''))
                pres.precio_venta1 = safe_dec(fila.get(f'{prefix}_p1'))
                pres.condicion2 = str(fila.get(f'{prefix}_c2', ''))
                pres.precio_venta2 = safe_dec(fila.get(f'{prefix}_p2'))
                pres.sync_estado = 'pendiente'
                
        db.session.commit()
        return jsonify({"status": "success", "message": "Datos guardados correctamente"})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500