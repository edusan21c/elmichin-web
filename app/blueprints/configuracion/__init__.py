# app/blueprints/configuracion/__init__.py
from flask import Blueprint

bp = Blueprint('configuracion', __name__, url_prefix='/configuracion')

from . import routes  # noqa: E402, F401
