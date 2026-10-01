# app/blueprints/reportes/__init__.py
from flask import Blueprint

bp = Blueprint('reportes', __name__, url_prefix='/reportes')

from . import routes  # noqa: E402, F401
