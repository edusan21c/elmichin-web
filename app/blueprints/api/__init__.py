# app/blueprints/api/__init__.py
from flask import Blueprint

bp = Blueprint('api', __name__, url_prefix='/api')

from . import sync       # noqa: E402, F401
from . import impresion  # noqa: E402, F401
