# scripts/crear_usuarios.py
# Modulo de gestion de usuarios (solo programador).
# Ejecutar UNA VEZ: python scripts\crear_usuarios.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== BLUEPRINT ====================
ARCHIVOS['app/blueprints/admin/__init__.py'] = '''# app/blueprints/admin/__init__.py
from flask import Blueprint

bp = Blueprint('admin', __name__, url_prefix='/admin')

from . import usuarios  # noqa: E402, F401
'''

ARCHIVOS['app/blueprints/admin/usuarios.py'] = '''# app/blueprints/admin/usuarios.py
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.usuario import Usuario
from app.models.tienda import Tienda
from app.utils.seguridad import hash_password
from app.utils.decorators import programador_requerido


@bp.route('/usuarios')
@login_required
@programador_requerido
def lista_usuarios():
    usuarios = Usuario.query.order_by(Usuario.id).all()
    tiendas = Tienda.query.filter_by(activa=True).all()
    return render_template(
        'admin/usuarios.html',
        usuarios=usuarios,
        tiendas=tiendas,
    )


@bp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
@programador_requerido
def nuevo_usuario():
    tiendas = Tienda.query.filter_by(activa=True).all()

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        rol = request.form.get('rol', 'operario')
        tienda_id = request.form.get('tienda_id', type=int)

        # Validaciones
        if not nombre or not username or not password:
            flash('Nombre, usuario y contraseña son obligatorios.', 'danger')
            return redirect(url_for('admin.nuevo_usuario'))

        if rol not in ('admin', 'programador', 'operario'):
            flash('Rol inválido.', 'danger')
            return redirect(url_for('admin.nuevo_usuario'))

        existente = Usuario.query.filter_by(username=username).first()
        if existente:
            flash(f'El usuario "{username}" ya existe.', 'danger')
            return redirect(url_for('admin.nuevo_usuario'))

        # Si es programador, no tiene tienda
        if rol == 'programador':
            tienda_id = None

        # Crear usuario
        nuevo = Usuario(
            nombre=nombre,
            username=username,
            password_hash=hash_password(password),
            rol=rol,
            tienda_id=tienda_id,
            activo=True,
        )
        db.session.add(nuevo)
        db.session.commit()

        flash(f'Usuario "{username}" creado correctamente.', 'success')
        return redirect(url_for('admin.lista_usuarios'))

    return render_template('admin/usuario_form.html',
                           usuario=None, tiendas=tiendas)


@bp.route('/usuarios/<int:uid>/editar', methods=['GET', 'POST'])
@login_required
@programador_requerido
def editar_usuario(uid):
    usuario = Usuario.query.get_or_404(uid)
    tiendas = Tienda.query.filter_by(activa=True).all()

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        rol = request.form.get('rol', 'operario')
        tienda_id = request.form.get('tienda_id', type=int)
        activo = request.form.get('activo') == 'on'

        if not nombre or not username:
            flash('Nombre y usuario son obligatorios.', 'danger')
            return redirect(url_for('admin.editar_usuario', uid=uid))

        if rol not in ('admin', 'programador', 'operario'):
            flash('Rol inválido.', 'danger')
            return redirect(url_for('admin.editar_usuario', uid=uid))

        # Verificar username único
        existente = Usuario.query.filter(
            Usuario.username == username,
            Usuario.id != uid
        ).first()
        if existente:
            flash(f'El usuario "{username}" ya está en uso.', 'danger')
            return redirect(url_for('admin.editar_usuario', uid=uid))

        # No permitir que el programador se desactive o cambie su rol
        if usuario.id == current_user.id:
            if not activo:
                flash('No puedes desactivar tu propio usuario.', 'danger')
                return redirect(url_for('admin.editar_usuario', uid=uid))
            if rol != 'programador':
                flash('No puedes cambiar tu propio rol.', 'danger')
                return redirect(url_for('admin.editar_usuario', uid=uid))

        # Actualizar
        usuario.nombre = nombre
        usuario.username = username
        usuario.rol = rol
        usuario.tienda_id = None if rol == 'programador' else tienda_id
        usuario.activo = activo

        if password:
            usuario.password_hash = hash_password(password)

        db.session.commit()
        flash(f'Usuario "{username}" actualizado.', 'success')
        return redirect(url_for('admin.lista_usuarios'))

    return render_template('admin/usuario_form.html',
                           usuario=usuario, tiendas=tiendas)


@bp.route('/usuarios/<int:uid>/eliminar', methods=['POST'])
@login_required
@programador_requerido
def eliminar_usuario(uid):
    usuario = Usuario.query.get_or_404(uid)

    if usuario.id == current_user.id:
        flash('No puedes eliminar tu propio usuario.', 'danger')
        return redirect(url_for('admin.lista_usuarios'))

    nombre = usuario.username
    db.session.delete(usuario)
    db.session.commit()
    flash(f'Usuario "{nombre}" eliminado.', 'success')
    return redirect(url_for('admin.lista_usuarios'))


@bp.route('/usuarios/<int:uid>/reset-password', methods=['POST'])
@login_required
@programador_requerido
def reset_password(uid):
    usuario = Usuario.query.get_or_404(uid)
    nueva = request.form.get('nueva_password', '').strip()
    if not nueva or len(nueva) < 4:
        flash('La contraseña debe tener al menos 4 caracteres.', 'danger')
        return redirect(url_for('admin.lista_usuarios'))

    usuario.password_hash = hash_password(nueva)
    db.session.commit()
    flash(f'Contraseña de "{usuario.username}" cambiada.', 'success')
    return redirect(url_for('admin.lista_usuarios'))
'''

# ==================== TEMPLATES ====================
ARCHIVOS['app/templates/admin/usuarios.html'] = '''{% extends 'base.html' %}
{% block titulo %}Usuarios{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-people"></i> Gestión de Usuarios
    </h1>
    <a href="{{ url_for('admin.nuevo_usuario') }}" class="btn btn-primary">
        <i class="bi bi-person-plus"></i> Nuevo usuario
    </a>
</div>

<div class="alert alert-info">
    <i class="bi bi-info-circle"></i>
    Solo el <strong>programador</strong> puede gestionar usuarios.
    Los roles disponibles son: <strong>programador</strong> (control total), 
    <strong>admin</strong> (dueño de tienda) y <strong>operario</strong> (cajero).
</div>

<div class="card">
    <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
                <tr>
                    <th>ID</th>
                    <th>Nombre</th>
                    <th>Usuario</th>
                    <th>Rol</th>
                    <th>Tienda</th>
                    <th class="text-center">Estado</th>
                    <th class="text-end">Acciones</th>
                </tr>
            </thead>
            <tbody>
                {% for u in usuarios %}
                <tr>
                    <td class="text-muted small">{{ u.id }}</td>
                    <td>{{ u.nombre }}</td>
                    <td><code>{{ u.username }}</code></td>
                    <td>
                        {% if u.rol == 'programador' %}
                            <span class="badge bg-danger">Programador</span>
                        {% elif u.rol == 'admin' %}
                            <span class="badge bg-warning text-dark">Admin</span>
                        {% else %}
                            <span class="badge bg-info text-dark">Operario</span>
                        {% endif %}
                    </td>
                    <td>
                        {% if u.tienda %}
                            {{ u.tienda.nombre }}
                        {% else %}
                            <span class="text-muted">—</span>
                        {% endif %}
                    </td>
                    <td class="text-center">
                        {% if u.activo %}
                            <span class="badge bg-success">Activo</span>
                        {% else %}
                            <span class="badge bg-secondary">Inactivo</span>
                        {% endif %}
                    </td>
                    <td class="text-end">
                        <a href="{{ url_for('admin.editar_usuario', uid=u.id) }}"
                           class="btn btn-sm btn-outline-primary">
                            <i class="bi bi-pencil"></i>
                        </a>
                        <button type="button" class="btn btn-sm btn-outline-warning"
                                data-bs-toggle="modal" data-bs-target="#modalReset{{ u.id }}">
                            <i class="bi bi-key"></i>
                        </button>
                        {% if u.id != current_user.id %}
                        <form method="POST" action="{{ url_for('admin.eliminar_usuario', uid=u.id) }}"
                              class="d-inline"
                              onsubmit="return confirm('¿Eliminar al usuario {{ u.username }}?');">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                            <button type="submit" class="btn btn-sm btn-outline-danger">
                                <i class="bi bi-trash"></i>
                            </button>
                        </form>
                        {% endif %}
                    </td>
                </tr>

                <!-- Modal reset password -->
                <div class="modal fade" id="modalReset{{ u.id }}" tabindex="-1">
                    <div class="modal-dialog">
                        <form method="POST" action="{{ url_for('admin.reset_password', uid=u.id) }}">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">Cambiar contraseña de {{ u.username }}</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                </div>
                                <div class="modal-body">
                                    <label class="form-label">Nueva contraseña</label>
                                    <input type="text" name="nueva_password" class="form-control" 
                                           required minlength="4" placeholder="Mínimo 4 caracteres">
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                                    <button type="submit" class="btn btn-warning">Cambiar contraseña</button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
'''

ARCHIVOS['app/templates/admin/usuario_form.html'] = '''{% extends 'base.html' %}
{% block titulo %}{{ 'Editar' if usuario else 'Nuevo' }} Usuario{% endblock %}

{% block contenido %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1 class="h3 mb-0">
        <i class="bi bi-{{ 'pencil' if usuario else 'person-plus' }}"></i>
        {{ 'Editar usuario' if usuario else 'Nuevo usuario' }}
    </h1>
    <a href="{{ url_for('admin.lista_usuarios') }}" class="btn btn-outline-secondary">
        <i class="bi bi-arrow-left"></i> Volver
    </a>
</div>

<div class="row justify-content-center">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-body">
                <form method="POST">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

                    <div class="mb-3">
                        <label class="form-label">Nombre completo *</label>
                        <input type="text" name="nombre" class="form-control" required
                               value="{{ usuario.nombre if usuario else '' }}"
                               placeholder="Ej: Juan Pérez">
                    </div>

                    <div class="mb-3">
                        <label class="form-label">Usuario (para login) *</label>
                        <input type="text" name="username" class="form-control" required
                               value="{{ usuario.username if usuario else '' }}"
                               placeholder="Ej: jperez"
                               autocomplete="off">
                        <small class="text-muted">Sin espacios, sin tildes. Es lo que se escribe al iniciar sesión.</small>
                    </div>

                    <div class="mb-3">
                        <label class="form-label">
                            Contraseña
                            {% if usuario %}<small class="text-muted">(dejar en blanco para no cambiar)</small>{% endif %}
                        </label>
                        <input type="text" name="password" class="form-control"
                               {% if not usuario %}required{% endif %}
                               placeholder="{{ 'Dejar en blanco para no cambiar' if usuario else 'Contraseña del usuario' }}"
                               autocomplete="off">
                    </div>

                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Rol *</label>
                            <select name="rol" class="form-select" required id="selector-rol">
                                <option value="operario" {% if usuario and usuario.rol == 'operario' %}selected{% endif %}>
                                    Operario (cajero)
                                </option>
                                <option value="admin" {% if usuario and usuario.rol == 'admin' %}selected{% endif %}>
                                    Admin (dueño de tienda)
                                </option>
                                <option value="programador" {% if usuario and usuario.rol == 'programador' %}selected{% endif %}>
                                    Programador (control total)
                                </option>
                            </select>
                        </div>

                        <div class="col-md-6 mb-3">
                            <label class="form-label">Tienda</label>
                            <select name="tienda_id" class="form-select" id="selector-tienda">
                                <option value="">— Sin tienda (solo programador) —</option>
                                {% for t in tiendas %}
                                <option value="{{ t.id }}"
                                        {% if usuario and usuario.tienda_id == t.id %}selected{% endif %}>
                                    {{ t.nombre }}
                                </option>
                                {% endfor %}
                            </select>
                            <small class="text-muted">El programador no necesita tienda.</small>
                        </div>
                    </div>

                    {% if usuario %}
                    <div class="form-check mb-3">
                        <input type="checkbox" name="activo" class="form-check-input" id="chk-activo"
                               {% if usuario.activo %}checked{% endif %}>
                        <label class="form-check-label" for="chk-activo">
                            Usuario activo (puede iniciar sesión)
                        </label>
                    </div>
                    {% endif %}

                    <hr>

                    <div class="d-flex justify-content-end gap-2">
                        <a href="{{ url_for('admin.lista_usuarios') }}" class="btn btn-outline-secondary">
                            Cancelar
                        </a>
                        <button type="submit" class="btn btn-primary">
                            <i class="bi bi-check-circle"></i> Guardar
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Info -->
        <div class="alert alert-light mt-3">
            <h6 class="mb-2"><i class="bi bi-info-circle"></i> Sobre los roles:</h6>
            <ul class="mb-0 small">
                <li><strong>Operario:</strong> solo puede facturar y ver reportes básicos.</li>
                <li><strong>Admin:</strong> puede facturar, gestionar inventario, ver reportes completos.</li>
                <li><strong>Programador:</strong> control total, incluye gestión de usuarios.</li>
            </ul>
        </div>
    </div>
</div>

<script>
    // Si el rol es programador, auto-seleccionar "sin tienda"
    document.getElementById('selector-rol').addEventListener('change', function() {
        const tiendaSelect = document.getElementById('selector-tienda');
        if (this.value === 'programador') {
            tiendaSelect.value = '';
        }
    });
</script>
{% endblock %}
'''


def main():
    print(f'Creando modulo de usuarios en: {RAIZ}')
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