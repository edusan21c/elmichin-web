# scripts/crear_configuracion.py
# Modulo de Configuracion (solo programador y admin).
# Ejecutar UNA VEZ: python scripts\crear_configuracion.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== BLUEPRINT ====================
ARCHIVOS['app/blueprints/configuracion/__init__.py'] = '''# app/blueprints/configuracion/__init__.py
from flask import Blueprint

bp = Blueprint('configuracion', __name__, url_prefix='/configuracion')

from . import routes  # noqa: E402, F401
'''

ARCHIVOS['app/blueprints/configuracion/routes.py'] = '''# app/blueprints/configuracion/routes.py
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.configuracion import Configuracion
from app.utils.decorators import admin_requerido


# Claves de configuracion con valores por defecto
PARAMETROS_DEFAULT = {
    'recargo_nequi': '0.4',
    'valor_bolsa': '100',
    'impresora_ip': '192.168.0.14',
    'impresora_puerto': '9100',
    'negocio_nombre': 'El Michín Dulcería',
    'negocio_nit': '80240907-X',
    'negocio_direccion': 'Cr 17M 67B-11 sur Lucero Bajo',
    'negocio_telefono': '301 467 5377',
    'negocio_slogan': 'Dulces momentos, precios dulces',
}


def obtener_valor(clave, default=''):
    """Lee un valor de la BD, o devuelve el default."""
    conf = Configuracion.query.filter_by(clave=clave).first()
    if conf:
        return conf.valor
    return PARAMETROS_DEFAULT.get(clave, default)


def guardar_valor(clave, valor):
    """Guarda un valor en la BD."""
    conf = Configuracion.query.filter_by(clave=clave).first()
    if conf:
        conf.valor = str(valor)
    else:
        conf = Configuracion(clave=clave, valor=str(valor))
        db.session.add(conf)


def cargar_todos():
    """Devuelve un dict con todos los parametros actuales."""
    resultado = {}
    for clave in PARAMETROS_DEFAULT.keys():
        resultado[clave] = obtener_valor(clave)
    return resultado


# ==================== RUTAS ====================
@bp.route('/', methods=['GET', 'POST'])
@login_required
@admin_requerido
def index():
    if request.method == 'POST':
        try:
            # Validar y guardar cada parametro
            parametros = {
                'recargo_nequi': request.form.get('recargo_nequi', '0.4').strip(),
                'valor_bolsa': request.form.get('valor_bolsa', '100').strip(),
                'impresora_ip': request.form.get('impresora_ip', '').strip(),
                'impresora_puerto': request.form.get('impresora_puerto', '9100').strip(),
                'negocio_nombre': request.form.get('negocio_nombre', '').strip(),
                'negocio_nit': request.form.get('negocio_nit', '').strip(),
                'negocio_direccion': request.form.get('negocio_direccion', '').strip(),
                'negocio_telefono': request.form.get('negocio_telefono', '').strip(),
                'negocio_slogan': request.form.get('negocio_slogan', '').strip(),
            }

            # Validaciones
            try:
                float(parametros['recargo_nequi'])
                int(parametros['valor_bolsa'])
                int(parametros['impresora_puerto'])
            except ValueError:
                flash('Recargo, valor bolsa y puerto deben ser numeros.', 'danger')
                return redirect(url_for('configuracion.index'))

            # Guardar
            for clave, valor in parametros.items():
                guardar_valor(clave, valor)

            db.session.commit()
            flash('Configuracion guardada correctamente.', 'success')
            return redirect(url_for('configuracion.index'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error guardando: {e}', 'danger')
            return redirect(url_for('configuracion.index'))

    # GET: mostrar formulario
    parametros = cargar_todos()
    return render_template('configuracion/index.html', config=parametros)
'''

# ==================== TEMPLATE ====================
ARCHIVOS['app/templates/configuracion/index.html'] = '''{% extends 'base.html' %}
{% block titulo %}Configuración{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-gear"></i> Configuración del Sistema
    </h1>
</div>

<div class="alert alert-info">
    <i class="bi bi-info-circle"></i>
    Estos valores se aplican en todo el sistema. Los cambios se guardan al presionar <strong>Guardar</strong>.
</div>

<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

    <div class="row g-3">
        <!-- ============ COLUMNA IZQUIERDA: NEGOCIO ============ -->
        <div class="col-lg-6">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <i class="bi bi-shop"></i> Datos del negocio
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <label class="form-label">Nombre del negocio</label>
                        <input type="text" name="negocio_nombre" class="form-control"
                               value="{{ config.negocio_nombre }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Slogan</label>
                        <input type="text" name="negocio_slogan" class="form-control"
                               value="{{ config.negocio_slogan }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">NIT</label>
                        <input type="text" name="negocio_nit" class="form-control"
                               value="{{ config.negocio_nit }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Dirección</label>
                        <input type="text" name="negocio_direccion" class="form-control"
                               value="{{ config.negocio_direccion }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Teléfono</label>
                        <input type="text" name="negocio_telefono" class="form-control"
                               value="{{ config.negocio_telefono }}">
                    </div>
                </div>
            </div>
        </div>

        <!-- ============ COLUMNA DERECHA: OPERATIVO ============ -->
        <div class="col-lg-6">
            <div class="card mb-3">
                <div class="card-header bg-success text-white">
                    <i class="bi bi-cash-coin"></i> Operación
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <label class="form-label">
                            Recargo Nequi/Daviplata (%)
                        </label>
                        <div class="input-group">
                            <input type="number" name="recargo_nequi" class="form-control"
                                   value="{{ config.recargo_nequi }}" step="0.01" min="0" max="10">
                            <span class="input-group-text">%</span>
                        </div>
                        <small class="text-muted">Ejemplo: 0.4 = 0.4%</small>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Valor de cada bolsa</label>
                        <div class="input-group">
                            <span class="input-group-text">$</span>
                            <input type="number" name="valor_bolsa" class="form-control"
                                   value="{{ config.valor_bolsa }}" min="0">
                        </div>
                        <small class="text-muted">Se cobra por unidad cuando el cliente pide bolsa</small>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header bg-warning text-dark">
                    <i class="bi bi-printer"></i> Impresora térmica
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <label class="form-label">IP de la impresora</label>
                        <input type="text" name="impresora_ip" class="form-control"
                               value="{{ config.impresora_ip }}" placeholder="192.168.0.14">
                        <small class="text-muted">IP en la red local</small>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Puerto</label>
                        <input type="number" name="impresora_puerto" class="form-control"
                               value="{{ config.impresora_puerto }}" min="1" max="65535">
                        <small class="text-muted">Estándar: 9100</small>
                    </div>
                </div>
            </div>
        </div>
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
{% endblock %}
'''


def main():
    print(f'Creando modulo de Configuracion en: {RAIZ}')
    print('-' * 60)
    for rel_path, contenido in ARCHIVOS.items():
        ruta = os.path.join(RAIZ, *rel_path.split('/'))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f'  OK  {rel_path}')
    print('-' * 60)
    print(f'Listo: {len(ARCHIVOS)} archivos creados.')


if __name__ == '__main__':
    main()