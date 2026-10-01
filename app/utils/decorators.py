# app/utils/decorators.py
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
