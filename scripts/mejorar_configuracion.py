# scripts/mejorar_configuracion.py
# Rehace el modulo de Configuracion con soporte multi-tienda.
# Ejecutar UNA VEZ: python scripts\mejorar_configuracion.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== ROUTES ====================
ARCHIVOS['app/blueprints/configuracion/routes.py'] = '''# app/blueprints/configuracion/routes.py
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
'''

# ==================== TEMPLATE ====================
ARCHIVOS['app/templates/configuracion/index.html'] = '''{% extends 'base.html' %}
{% block titulo %}Configuración{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-gear"></i> Configuración
        {% if current_user.es_programador() and tiendas|length > 1 %}
            <small class="text-muted">- Editando:
                <select id="selector-tienda" class="form-select form-select-sm d-inline-block" style="width:auto;">
                    {% for t in tiendas %}
                        <option value="{{ t.id }}" {% if t.id == tienda_id %}selected{% endif %}>{{ t.nombre }}</option>
                    {% endfor %}
                </select>
            </small>
        {% endif %}
    </h1>
</div>

<div class="alert alert-info">
    <i class="bi bi-info-circle"></i>
    Los datos marcados como <span class="badge bg-primary">Global</span> se comparten entre todas las tiendas.
    Los datos <span class="badge bg-success">Por tienda</span> son específicos de cada local.
</div>

<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="hidden" name="tienda_id" value="{{ tienda_id or '' }}">

    <div class="row g-3">
        <!-- ============ DATOS GLOBALES ============ -->
        {% if current_user.es_programador() or not tienda_id %}
        <div class="col-12">
            <div class="card border-primary">
                <div class="card-header bg-primary text-white">
                    <i class="bi bi-globe"></i> Datos globales
                    <span class="badge bg-light text-primary ms-2">Compartido entre todas las tiendas</span>
                </div>
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-6">
                            <label class="form-label">Nombre del negocio</label>
                            <input type="text" name="negocio_nombre" class="form-control"
                                   value="{{ config_global.negocio_nombre }}"
                                   {% if not current_user.es_programador() %}readonly{% endif %}>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Slogan</label>
                            <input type="text" name="negocio_slogan" class="form-control"
                                   value="{{ config_global.negocio_slogan }}"
                                   {% if not current_user.es_programador() %}readonly{% endif %}>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">NIT</label>
                            <input type="text" name="negocio_nit" class="form-control"
                                   value="{{ config_global.negocio_nit }}"
                                   {% if not current_user.es_programador() %}readonly{% endif %}>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Recargo Nequi/Daviplata (%)</label>
                            <div class="input-group">
                                <input type="number" name="recargo_nequi" class="form-control"
                                       value="{{ config_global.recargo_nequi }}" step="0.01" min="0" max="10"
                                       {% if not current_user.es_programador() %}readonly{% endif %}>
                                <span class="input-group-text">%</span>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Valor de cada bolsa</label>
                            <div class="input-group">
                                <span class="input-group-text">$</span>
                                <input type="number" name="valor_bolsa" class="form-control"
                                       value="{{ config_global.valor_bolsa }}" min="0"
                                       {% if not current_user.es_programador() %}readonly{% endif %}>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}

        <!-- ============ DATOS POR TIENDA ============ -->
        {% if tienda_id %}
        <div class="col-12">
            <div class="card border-success">
                <div class="card-header bg-success text-white">
                    <i class="bi bi-shop"></i> Datos de esta tienda
                    <span class="badge bg-light text-success ms-2">Solo para esta tienda</span>
                </div>
                <div class="card-body">
                    <div class="row g-3">
                        <div class="col-md-6">
                            <label class="form-label">Dirección</label>
                            <input type="text" name="negocio_direccion" class="form-control"
                                   value="{{ config_tienda.negocio_direccion }}">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Teléfono</label>
                            <input type="text" name="negocio_telefono" class="form-control"
                                   value="{{ config_tienda.negocio_telefono }}">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">IP de la impresora</label>
                            <input type="text" name="impresora_ip" class="form-control"
                                   value="{{ config_tienda.impresora_ip }}" placeholder="192.168.0.14">
                            <small class="text-muted">IP en la red local de esta tienda</small>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Puerto de la impresora</label>
                            <input type="number" name="impresora_puerto" class="form-control"
                                   value="{{ config_tienda.impresora_puerto }}" min="1" max="65535">
                        </div>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
    </div>

    <!-- ============ BOTONES ============ -->
    <div class="mt-4 d-flex justify-content-end gap-2">
        <a href="{{ url_for('dashboard.index') }}" class="btn btn-outline-secondary">
            Cancelar
        </a>
        <button type="submit" class="btn btn-primary btn-lg">
            <i class="bi bi-check-circle"></i> Guardar configuración
        </button>
    </div>
</form>

<script>
const st = document.getElementById('selector-tienda');
if (st) {
    st.addEventListener('change', function() {
        const url = new URL(window.location.href);
        url.searchParams.set('tienda', this.value);
        window.location.href = url.toString();
    });
}
</script>
{% endblock %}
'''


def main():
    print(f'Mejorando modulo de Configuracion en: {RAIZ}')
    print('-' * 60)
    for rel_path, contenido in ARCHIVOS.items():
        ruta = os.path.join(RAIZ, *rel_path.split('/'))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f'  OK  {rel_path}')
    print('-' * 60)
    print(f'Listo: {len(ARCHIVOS)} archivos actualizados.')


if __name__ == '__main__':
    main()