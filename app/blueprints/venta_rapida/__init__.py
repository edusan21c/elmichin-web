# app/blueprints/venta_rapida/__init__.py
from flask import Blueprint

bp = Blueprint('venta_rapida', __name__, url_prefix='/venta-rapida')

from . import routes  # noqa: E402, F401
