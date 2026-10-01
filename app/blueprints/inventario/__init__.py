# app/blueprints/inventario/__init__.py
from flask import Blueprint

bp = Blueprint('inventario', __name__, url_prefix='/inventario')

from . import routes  # noqa: E402, F401
