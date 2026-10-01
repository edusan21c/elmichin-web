# app/blueprints/admin/usuarios.py
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
