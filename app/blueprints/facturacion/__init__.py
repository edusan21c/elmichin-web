# app/blueprints/facturacion/__init__.py
from flask import Blueprint

bp = Blueprint('facturacion', __name__, url_prefix='/facturacion')

from . import routes  # noqa: E402, F401
