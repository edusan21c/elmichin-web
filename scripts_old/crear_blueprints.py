# scripts/crear_blueprints.py
# Crea blueprints auth y dashboard + templates base + utilidades.
# Ejecutar UNA SOLA VEZ: python scripts\crear_blueprints.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ARCHIVOS = {}

# ==================== UTILS ====================
ARCHIVOS['app/utils/__init__.py'] = ''

ARCHIVOS['app/utils/seguridad.py'] = '''# app/utils/seguridad.py
"""Utilidades de seguridad: hash de contraseñas con bcrypt."""
import bcrypt


def hash_password(password: str) -> str:
    """Genera un hash bcrypt de una contraseña."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verificar_password(password_hash: str, password: str) -> bool:
    """Verifica si una contraseña coincide con su hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False
'''

ARCHIVOS['app/utils/decorators.py'] = '''# app/utils/decorators.py
"""Decoradores para control de acceso por roles."""
from functools import wraps
from flask import abort
from flask_login import current_user


def rol_requerido(*roles):
    """Restringe el acceso a ciertos roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.rol not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def programador_requerido(f):
    return rol_requerido('programador')(f)


def admin_requerido(f):
    return rol_requerido('admin', 'programador')(f)


def operario_o_superior(f):
    return rol_requerido('admin', 'programador', 'operario')(f)
'''

# ==================== BLUEPRINTS ====================
ARCHIVOS['app/blueprints/__init__.py'] = ''

# ---------- auth ----------
ARCHIVOS['app/blueprints/auth/__init__.py'] = '''# app/blueprints/auth/__init__.py
from flask import Blueprint

bp = Blueprint('auth', __name__)

from . import routes  # noqa: E402, F401
'''

ARCHIVOS['app/blueprints/auth/forms.py'] = '''# app/blueprints/auth/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    username = StringField(
        'Usuario',
        validators=[DataRequired(message='Ingresa tu usuario'), Length(max=100)]
    )
    password = PasswordField(
        'Contraseña',
        validators=[DataRequired(message='Ingresa tu contraseña')]
    )
    remember = BooleanField('Recordarme')
    submit = SubmitField('Ingresar')
'''

ARCHIVOS['app/blueprints/auth/routes.py'] = '''# app/blueprints/auth/routes.py
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from . import bp
from .forms import LoginForm
from app.models.usuario import Usuario
from app.utils.seguridad import verificar_password


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(username=form.username.data.strip()).first()

        if user and verificar_password(user.password_hash, form.password.data):
            if not user.activo:
                flash('Tu usuario está desactivado. Contacta al administrador.', 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            if next_page and not next_page.startswith('/'):
                next_page = None
            return redirect(next_page or url_for('dashboard.index'))

        flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))
'''

# ---------- dashboard ----------
ARCHIVOS['app/blueprints/dashboard/__init__.py'] = '''# app/blueprints/dashboard/__init__.py
from flask import Blueprint

bp = Blueprint('dashboard', __name__)

from . import routes  # noqa: E402, F401
'''

ARCHIVOS['app/blueprints/dashboard/routes.py'] = '''# app/blueprints/dashboard/routes.py
from flask import render_template, current_app
from flask_login import login_required, current_user
from . import bp
from app.models.tienda import Tienda
from app.models.producto import Producto


@bp.route('/')
@login_required
def index():
    context = {
        'titulo': 'Inicio',
        'modo': current_app.config.get('MODO', 'desconocido'),
        'tienda_id': current_app.config.get('TIENDA_ID', 0),
        'total_productos': Producto.query.count(),
        'total_tiendas': Tienda.query.count(),
    }
    return render_template('dashboard/index.html', **context)
'''

# ==================== TEMPLATES ====================
ARCHIVOS['app/templates/base.html'] = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block titulo %}El Michín{% endblock %} - El Michín</title>

    <!-- Bootstrap 5 -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">

    <!-- Estilos personalizados -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/custom.css') }}">
    {% block estilos_extra %}{% endblock %}
</head>
<body class="bg-light">

{% if current_user.is_authenticated %}
    {% include 'layout/navbar.html' %}
    <div class="container-fluid">
        <div class="row">
            {% include 'layout/sidebar.html' %}
            <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4 py-4">
                {% include 'layout/flash.html' %}
                {% block contenido %}{% endblock %}
            </main>
        </div>
    </div>
{% else %}
    <main class="container">
        {% include 'layout/flash.html' %}
        {% block contenido_publico %}{% endblock %}
    </main>
{% endif %}

<!-- Bootstrap 5 JS -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
{% block scripts_extra %}{% endblock %}
</body>
</html>
'''

ARCHIVOS['app/templates/layout/navbar.html'] = '''<nav class="navbar navbar-dark bg-dark sticky-top px-3">
    <a class="navbar-brand d-flex align-items-center" href="{{ url_for('dashboard.index') }}">
        <span style="font-size: 1.5rem;">🐱</span>
        <span class="ms-2 fw-bold">EL MICHÍN</span>
    </a>
    <div class="d-flex align-items-center text-white">
        <span class="me-3">
            <i class="bi bi-person-circle"></i>
            {{ current_user.nombre }} <small class="text-muted">({{ current_user.rol }})</small>
        </span>
        <a href="{{ url_for('auth.logout') }}" class="btn btn-outline-light btn-sm">
            <i class="bi bi-box-arrow-right"></i> Salir
        </a>
    </div>
</nav>
'''

ARCHIVOS['app/templates/layout/sidebar.html'] = '''<nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar border-end" style="min-height: calc(100vh - 56px);">
    <div class="position-sticky pt-3">
        <ul class="nav flex-column">
            <li class="nav-item">
                <a class="nav-link {% if request.endpoint == 'dashboard.index' %}active{% endif %}"
                   href="{{ url_for('dashboard.index') }}">
                    <i class="bi bi-house-door"></i> Inicio
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-box-seam"></i> Inventario <small class="text-muted">(pronto)</small>
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-receipt"></i> Facturación <small class="text-muted">(pronto)</small>
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-graph-up"></i> Reportes <small class="text-muted">(pronto)</small>
                </a>
            </li>
        </ul>
    </div>
</nav>
'''

ARCHIVOS['app/templates/layout/flash.html'] = '''{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        {% for categoria, mensaje in messages %}
            <div class="alert alert-{{ categoria if categoria != 'message' else 'info' }} alert-dismissible fade show" role="alert">
                {{ mensaje }}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        {% endfor %}
    {% endif %}
{% endwith %}
'''

ARCHIVOS['app/templates/auth/login.html'] = '''{% extends 'base.html' %}
{% block titulo %}Iniciar Sesión{% endblock %}

{% block contenido_publico %}
<div class="row justify-content-center mt-5">
    <div class="col-md-5 col-lg-4">
        <div class="card shadow">
            <div class="card-body p-4">
                <div class="text-center mb-4">
                    <div style="font-size: 3rem;">🐱</div>
                    <h3 class="fw-bold mb-0">EL MICHÍN</h3>
                    <small class="text-muted">Sistema de Gestión</small>
                </div>

                <form method="POST" novalidate>
                    {{ form.hidden_tag() }}

                    <div class="mb-3">
                        {{ form.username.label(class="form-label") }}
                        {{ form.username(class="form-control", placeholder="Usuario") }}
                        {% for error in form.username.errors %}
                            <div class="text-danger small">{{ error }}</div>
                        {% endfor %}
                    </div>

                    <div class="mb-3">
                        {{ form.password.label(class="form-label") }}
                        {{ form.password(class="form-control", placeholder="Contraseña") }}
                        {% for error in form.password.errors %}
                            <div class="text-danger small">{{ error }}</div>
                        {% endfor %}
                    </div>

                    <div class="form-check mb-3">
                        {{ form.remember(class="form-check-input") }}
                        {{ form.remember.label(class="form-check-label") }}
                    </div>

                    <button type="submit" class="btn btn-primary w-100">
                        <i class="bi bi-box-arrow-in-right"></i> Ingresar
                    </button>
                </form>
            </div>
        </div>
        <p class="text-center text-muted mt-3 small">
            © El Michín - Sistema Interno
        </p>
    </div>
</div>
{% endblock %}
'''

ARCHIVOS['app/templates/dashboard/index.html'] = '''{% extends 'base.html' %}
{% block titulo %}Inicio{% endblock %}

{% block contenido %}
<h1 class="h3 mb-4">🐱 ¡Hola, {{ current_user.nombre }}!</h1>

<div class="row g-3 mb-4">
    <div class="col-md-3">
        <div class="card border-primary">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <div class="text-muted small">Productos</div>
                        <div class="fs-3 fw-bold text-primary">{{ total_productos }}</div>
                    </div>
                    <i class="bi bi-box-seam fs-1 text-primary opacity-50"></i>
                </div>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card border-success">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <div class="text-muted small">Tiendas</div>
                        <div class="fs-3 fw-bold text-success">{{ total_tiendas }}</div>
                    </div>
                    <i class="bi bi-shop fs-1 text-success opacity-50"></i>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="card">
    <div class="card-header bg-white">
        <i class="bi bi-info-circle"></i> Estado del sistema
    </div>
    <div class="card-body">
        <ul class="mb-0">
            <li><strong>Modo:</strong> {{ modo }}</li>
            <li><strong>Tienda ID:</strong> {{ tienda_id }}</li>
            <li><strong>Rol:</strong> {{ current_user.rol }}</li>
        </ul>
    </div>
</div>
{% endblock %}
'''

ARCHIVOS['app/static/css/custom.css'] = '''/* Estilos personalizados - El Michín */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.navbar-brand {
    letter-spacing: 1px;
}

.sidebar .nav-link {
    color: #333;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 2px;
}

.sidebar .nav-link:hover:not(.disabled) {
    background-color: #e9ecef;
}

.sidebar .nav-link.active {
    background-color: #0d6efd;
    color: white;
}

.card {
    border-radius: 10px;
}

.btn {
    border-radius: 8px;
}
'''


def main():
    print(f'Creando blueprints y templates en: {RAIZ}')
    print('-' * 60)

    for rel_path, contenido in ARCHIVOS.items():
        ruta = os.path.join(RAIZ, *rel_path.split('/'))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f'  OK  {rel_path}')

    print('-' * 60)
    print(f'Listo: {len(ARCHIVOS)} archivos creados correctamente.')


if __name__ == '__main__':
    main()