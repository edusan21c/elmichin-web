# app/blueprints/estadisticas/__init__.py
from flask import Blueprint

bp = Blueprint('estadisticas', __name__, url_prefix='/estadisticas')

from . import routes  # noqa: E402, F401
