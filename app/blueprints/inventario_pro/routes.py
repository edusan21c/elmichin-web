from flask import render_template, jsonify, request, current_app, flash, redirect, url_for
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from decimal import Decimal
import os
import time
from PIL import Image
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

# CANDADO DE SEGURIDAD: Verifica que estemos en la Central
def verificar_central():
    if current_app.config.get('MODO') != 'central':
        return False
    return True

@bp.route('/')
@login_required
def index():
    if not current_user.es_programador():
        return "Acceso denegado. Solo el programador puede ver esta página.", 403
    
    # Si estamos en una tienda (T1 o T2), bloqueamos el acceso
    if not verificar_central():
        flash('El Inventario Pro solo está disponible desde la Central.', 'warning')
        return redirect(url_for('dashboard.index'))
        
    return render_template('inventario_pro/index.html')

@bp.route('/api/data')
@login_required
def get_data():
    if not verificar_central():
        return jsonify({"status": "error", "message": "Solo disponible en la Central"}), 403

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
            'imagen': p.imagen or '',
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
    if not current_user.es_programador() or not verificar_central():
        return jsonify({"status": "error", "message": "No tienes permiso."}), 403
        
    cambios = request.json
    try:
        for fila in cambios:
            prod_id = fila.get('id')
            nuevo_nombre = fila.get('nombre')
            nuevo_codigo = fila.get('codigo_barras') or None
            
            # BLINDAJE 1: Evitar nombres duplicados
            existe_otro = Producto.query.filter(Producto.nombre == nuevo_nombre, Producto.id != prod_id).first()
            if existe_otro:
                return jsonify({"status": "error", "message": f"¡ALTO! Ya existe un producto llamado '{nuevo_nombre}'. No se puede repetir."}), 400

            if prod_id and str(prod_id).strip() != '':
                prod = Producto.query.get(int(prod_id))
            else:
                codigo_ingresado = nuevo_codigo
                if not codigo_ingresado:
                    while True:
                        nuevo_codigo_gen = "200" + str(random.randint(100000000, 999999999))
                        if not Producto.query.filter_by(codigo_barras=nuevo_codigo_gen).first():
                            codigo_ingresado = nuevo_codigo_gen
                            break
                            
                prod = Producto(
                    nombre=nuevo_nombre,
                    categoria=fila.get('categoria'),
                    codigo_barras=codigo_ingresado,
                    codigo_global=str(uuid.uuid4())
                )
                db.session.add(prod)
                db.session.flush()

            if not prod: continue
            
            # BLINDAJE 2: Renombrar la foto (respetando el sufijo de tiempo) si cambia el código
            codigo_viejo = prod.codigo_barras
            if codigo_viejo and nuevo_codigo and codigo_viejo != nuevo_codigo:
                BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
                img_dir = os.path.join(BASE_DIR, 'app', 'static', 'img', 'productos')
                
                if prod.imagen and codigo_viejo in prod.imagen:
                    nombre_viejo_img = prod.imagen
                    nombre_nuevo_img = prod.imagen.replace(codigo_viejo, nuevo_codigo)
                    
                    ruta_vieja = os.path.join(img_dir, nombre_viejo_img)
                    ruta_nueva = os.path.join(img_dir, nombre_nuevo_img)
                    
                    if os.path.exists(ruta_vieja):
                        if os.path.exists(ruta_nueva):
                            os.remove(ruta_nueva)
                        os.rename(ruta_vieja, ruta_nueva)
                        prod.imagen = nombre_nuevo_img
            
            prod.nombre = nuevo_nombre
            prod.categoria = fila.get('categoria')
            prod.codigo_barras = nuevo_codigo
            
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
        return jsonify({"status": "success", "message": "Datos guardados y foto sincronizada correctamente."})
    except Exception as e:
        db.session.rollback()
        print(f"ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/upload-foto', methods=['POST'])
@login_required
def upload_foto():
    if not current_user.es_programador() or not verificar_central():
        return jsonify({"status": "error", "message": "No tienes permiso."}), 403

    prod_id = request.form.get('producto_id')
    file = request.files.get('foto')

    if not prod_id or not file:
        return jsonify({"status": "error", "message": "Faltan datos o archivo"}), 400

    prod = Producto.query.get(int(prod_id))
    if not prod:
        return jsonify({"status": "error", "message": "Producto no encontrado"}), 404

    codigo = prod.codigo_barras or f"PROD-{prod.id}"
    
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    ORIGEN = os.path.join(BASE_DIR, 'data', 'imagenes')
    DESTINO = os.path.join(BASE_DIR, 'app', 'static', 'img', 'productos')

    if not os.path.exists(ORIGEN):
        os.makedirs(ORIGEN)
    if not os.path.exists(DESTINO):
        os.makedirs(DESTINO)

    ruta_original = os.path.join(ORIGEN, f"{codigo}.jpeg")
    file.save(ruta_original)

    try:
        # EL TRUCO MÁGICO: Agregar un sufijo de tiempo (timestamp) al nombre del archivo
        # Así el navegador siempre verá un archivo nuevo y descargará la imagen real.
        timestamp = int(time.time())
        nombre_webp = f"{codigo}_v{timestamp}.webp"
        ruta_destino = os.path.join(DESTINO, nombre_webp)
        
        img = Image.open(ruta_original).convert("RGB")
        img.thumbnail((150, 150))
        img.save(ruta_destino, "WEBP", quality=80)

        # Eliminamos la foto anterior para no llenar el disco duro de basura
        if prod.imagen and prod.imagen != nombre_webp:
            ruta_foto_vieja = os.path.join(DESTINO, prod.imagen)
            if os.path.exists(ruta_foto_vieja):
                try:
                    os.remove(ruta_foto_vieja)
                except Exception:
                    pass

        # Actualizamos la base de datos con el nombre nuevo que incluye la versión
        prod.imagen = nombre_webp
        ProductoTienda.query.filter_by(producto_id=prod.id).update({'sync_estado': 'pendiente'})
        db.session.commit()

        return jsonify({"status": "ok", "message": "Foto guardada con nueva versión"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al procesar la foto: {str(e)}"}), 500