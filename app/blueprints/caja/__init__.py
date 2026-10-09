# app/blueprints/caja/__init__.py
from flask import Blueprint

bp = Blueprint('caja', __name__, url_prefix='/caja')

from . import routes  # noqa: E402, F401