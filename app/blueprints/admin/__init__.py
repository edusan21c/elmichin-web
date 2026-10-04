# app/blueprints/admin/__init__.py
from flask import Blueprint

bp = Blueprint('admin', __name__, url_prefix='/admin')

from . import usuarios    # noqa: E402, F401
from . import auditoria   # noqa: E402, F401
from . import monitor     # noqa: E402, F401
