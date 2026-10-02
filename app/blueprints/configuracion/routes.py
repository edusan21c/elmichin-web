# app/blueprints/configuracion/routes.py
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.configuracion import Configuracion
from app.models.tienda import Tienda
from app.utils.decorators import admin_requerido


# Parametros: (clave, valor_default, es_global)
PARAMETROS = [
    # Globales
    ('negocio_nombre',    'El Michín Dulcería',                    True),
    ('negocio_slogan',    'Dulces momentos, precios dulces',       True),
    ('negocio_nit',       '80240907-X',                             True),
    ('recargo_nequi',     '0.4',                                    True),
    ('valor_bolsa',       '100',                                    True),
    # Por tienda
    ('negocio_direccion', '',                                       False),
    ('negocio_telefono',  '',                                       False),
    ('impresora_ip',      '192.168.0.14',                           False),
    ('impresora_puerto',  '9100',                                   False),
]


def get_valor(clave, tienda_id=None):
    """Lee un valor de la BD. Si no existe, devuelve el default."""
    q = Configuracion.query.filter_by(clave=clave)
    if tienda_id:
        q = q.filter_by(tienda_id=tienda_id)
    else:
        q = q.filter(Configuracion.tienda_id.is_(None))
    conf = q.first()
    if conf:
        return conf.valor
    # Default
    for k, v, is_global in PARAMETROS:
        if k == clave:
            return v
    return ''


def set_valor(clave, valor, tienda_id=None):
    """Guarda un valor. Actualiza si existe, crea si no."""
    q = Configuracion.query.filter_by(clave=clave)
    if tienda_id:
        q = q.filter_by(tienda_id=tienda_id)
    else:
        q = q.filter(Configuracion.tienda_id.is_(None))
    conf = q.first()

    if conf:
        conf.valor = str(valor)
    else:
        conf = Configuracion(tienda_id=tienda_id, clave=clave, valor=str(valor))
        db.session.add(conf)


def cargar_config(tienda_id=None):
    """Devuelve dict con los valores de una tienda o globales."""
    resultado = {}
    for clave, default, es_global in PARAMETROS:
        if es_global:
            resultado[clave] = get_valor(clave, None)
        else:
            if tienda_id:
                # Buscar valor de la tienda, si no existe usar default
                valor = get_valor(clave, tienda_id)
                resultado[clave] = valor if valor else default
            else:
                resultado[clave] = default
    return resultado


@bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_requerido
def index():
    tiendas = Tienda.query.filter_by(activa=True).order_by(Tienda.id).all()

    # Determinar tienda seleccionada
    if current_user.es_programador():
        tienda_id = request.args.get('tienda', type=int)
    else:
        tienda_id = current_user.tienda_id

    # Si es POST: guardar
    if request.method == 'POST':
        tienda_post = request.form.get('tienda_id', type=int)
        # Validar permiso: programador puede todo, admin solo su tienda
        if not current_user.es_programador():
            tienda_post = current_user.tienda_id

        try:
            for clave, default, es_global in PARAMETROS:
                valor = request.form.get(clave, '').strip()
                if not valor:
                    continue

                if es_global:
                    if current_user.es_programador():
                        set_valor(clave, valor, None)
                else:
                    if tienda_post:
                        set_valor(clave, valor, tienda_post)

            # Validaciones numericas
            try:
                float(request.form.get('recargo_nequi', 0.4))
                int(request.form.get('valor_bolsa', 100))
                int(request.form.get('impresora_puerto', 9100))
            except ValueError:
                flash('Hay valores numericos invalidos.', 'danger')
                return redirect(url_for('configuracion.index', tienda=tienda_post))

            db.session.commit()
            flash('Configuracion guardada correctamente.', 'success')
            return redirect(url_for('configuracion.index', tienda=tienda_post))

        except Exception as e:
            db.session.rollback()
            flash(f'Error guardando: {e}', 'danger')
            return redirect(url_for('configuracion.index', tienda=tienda_post))

    # GET: mostrar
    config_global = cargar_config(None)
    config_tienda = cargar_config(tienda_id) if tienda_id else {}

    return render_template(
        'configuracion/index.html',
        config_global=config_global,
        config_tienda=config_tienda,
        tiendas=tiendas,
        tienda_id=tienda_id,
    )
