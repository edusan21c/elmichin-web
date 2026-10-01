# app/utils/seguridad.py
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
