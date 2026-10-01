# app/blueprints/dashboard/routes.py
from flask import render_template, current_app
from flask_login import login_required, current_user
from . import bp
from app.models.tienda import Tienda
from app.models.producto import Producto


@bp.route('/')
@login_required
def index():
    context = {
        'titulo': 'Inicio',
        'modo': current_app.config.get('MODO', 'desconocido'),
        'tienda_id': current_app.config.get('TIENDA_ID', 0),
        'total_productos': Producto.query.count(),
        'total_tiendas': Tienda.query.count(),
    }
    return render_template('dashboard/index.html', **context)
