# app/blueprints/auth/routes.py
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

            # Auditoría: login exitoso
            from app.services.auditoria_service import registrar_auditoria
            registrar_auditoria('login', f'Login OK: {user.username}')

            next_page = request.args.get('next')
            if next_page and not next_page.startswith('/'):
                next_page = None
            return redirect(next_page or url_for('dashboard.index'))

        # Auditoría: login fallido
        from app.services.auditoria_service import registrar_auditoria
        intento = form.username.data.strip() if form.username.data else 'sin username'
        registrar_auditoria('login_fallido', f'Intento con usuario: {intento}')

        flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    # Auditoría: logout (antes de logout_user para capturar current_user)
    from app.services.auditoria_service import registrar_auditoria
    registrar_auditoria('logout', f'Logout: {current_user.username}')

    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))
