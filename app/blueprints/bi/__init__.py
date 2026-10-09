# app/blueprints/bi/__init__.py
from flask import Blueprint

bp = Blueprint('bi', __name__, url_prefix='/bi')

from . import routes  # noqa: E402, F401