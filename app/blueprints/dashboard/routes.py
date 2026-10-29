# app/blueprints/dashboard/routes.py
from flask import render_template, session, current_app, request
from flask_login import login_required, current_user
from . import bp
from app.models.producto import Producto
from app.models.tienda import Tienda

def tienda_actual():
    from flask import session, current_app
    from app.models.tienda import Tienda

    if current_app.config.get('MODO') == 'central' and (current_user.es_programador() or current_user.es_admin()):
        tid = request.args.get('tienda', type=int)
        if tid:
            session['tienda_actual_id'] = tid
            return tid
        if session.get('tienda_actual_id'):
            return session.get('tienda_actual_id')
        primera = Tienda.query.filter_by(activa=True).first()
        return primera.id if primera else None

    if current_user.tienda_id:
        return current_user.tienda_id

    return current_app.config.get('TIENDA_ID')


@bp.route('/')
@login_required
def index():
    tiendas = Tienda.query.filter_by(activa=True).all()
    total_productos = Producto.query.filter(Producto.categoria != 'INACTIVO').count()
    total_tiendas = len(tiendas)
    t_actual = tienda_actual()

    return render_template(
        'dashboard/index.html',
        tiendas=tiendas,
        tienda_actual=t_actual,
        total_productos=total_productos,
        total_tiendas=total_tiendas
    )