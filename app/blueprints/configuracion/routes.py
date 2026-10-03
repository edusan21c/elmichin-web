# app/blueprints/configuracion/routes.py
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.configuracion import Configuracion
from app.models.tienda import Tienda
from app.utils.decorators import admin_requerido, programador_requerido
from app.services import updater_service


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
    q = Configuracion.query.filter_by(clave=clave)
    if tienda_id:
        q = q.filter_by(tienda_id=tienda_id)
    else:
        q = q.filter(Configuracion.tienda_id.is_(None))
    conf = q.first()
    if conf:
        return conf.valor
    for k, v, is_global in PARAMETROS:
        if k == clave:
            return v
    return ''


def set_valor(clave, valor, tienda_id=None):
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
    resultado = {}
    for clave, default, es_global in PARAMETROS:
        if es_global:
            resultado[clave] = get_valor(clave, None)
        else:
            if tienda_id:
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

    if current_user.es_programador():
        tienda_id = request.args.get('tienda', type=int)
        if not tienda_id and tiendas:
            tienda_id = tiendas[0].id
    else:
        tienda_id = current_user.tienda_id

    if request.method == 'POST':
        tienda_post = request.form.get('tienda_id', type=int)
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

    config_global = cargar_config(None)
    config_tienda = cargar_config(tienda_id) if tienda_id else {}

    # Version actual
    version_local = updater_service.get_version_local()

    return render_template(
        'configuracion/index.html',
        config_global=config_global,
        config_tienda=config_tienda,
        tiendas=tiendas,
        tienda_id=tienda_id,
        version_local=version_local,
    )


# ==================== API VERSION / UPDATE ====================
@bp.route('/api/version', methods=['GET'])
@login_required
@programador_requerido
def api_version():
    """Devuelve la version local y si hay actualizacion disponible."""
    try:
        hay, local, remota = updater_service.hay_actualizacion()
        return jsonify({
            'ok': True,
            'version_local': local,
            'version_remota': remota,
            'hay_actualizacion': hay,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/actualizar', methods=['POST'])
@login_required
@programador_requerido
def api_actualizar():
    """Lanza la actualizacion."""
    exito, mensaje = updater_service.lanzar_actualizacion()
    return jsonify({'ok': exito, 'mensaje': mensaje})


@bp.route('/api/estado-actualizacion', methods=['GET'])
@login_required
@programador_requerido
def api_estado_actualizacion():
    """Consulta el estado actual de la actualizacion."""
    estado = updater_service.leer_estado()
    if not estado:
        return jsonify({
            'ok': True,
            'en_progreso': False,
        })
    return jsonify({
        'ok': True,
        'en_progreso': estado.get('estado') == 'en_progreso',
        'estado': estado.get('estado'),
        'paso': estado.get('paso', ''),
        'progreso': estado.get('progreso', 0),
        'mensaje': estado.get('mensaje', ''),
    })