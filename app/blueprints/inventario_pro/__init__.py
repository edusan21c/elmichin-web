from flask import Blueprint

bp = Blueprint('inventario_pro', __name__)

from . import routes