# app/blueprints/dashboard/__init__.py
from flask import Blueprint

bp = Blueprint('dashboard', __name__)

from . import routes  # noqa: E402, F401
