# app/__init__.py
from datetime import datetime, timedelta
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .extensions import db, migrate, login_manager, csrf
from config import get_config


def hora_local():
    """Devuelve la hora actual en zona horaria de Colombia (UTC-5)."""
    return datetime.utcnow() - timedelta(hours=5)


def create_app(config_class=None):
    """Factory de la aplicación Flask."""
    app = Flask(__name__)

    # ============ ProxyFix ============
    # Confiar en los headers X-Forwarded-* que envía Cloudflare Tunnel
    # IMPORTANTE: debe ir ANTES de cargar la configuración
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1,
    )

    # ============ Cargar configuración ============
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # ============ Inicializar extensiones ============
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # ============ Importar modelos (para que Alembic los detecte) ============
    from .models import usuario, tienda, producto, cliente, factura
    from .models import pago, venta, borrador, configuracion, sync_log

    # ============ Configurar login manager ============
    from .models.usuario import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # ============ Registrar blueprints ============
    from .blueprints.auth import bp as auth_bp
    from .blueprints.dashboard import bp as dashboard_bp
    from .blueprints.inventario import bp as inventario_bp
    from .blueprints.facturacion import bp as facturacion_bp
    from .blueprints.reportes import bp as reportes_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(facturacion_bp)
    app.register_blueprint(reportes_bp)

    # Si existe el módulo admin, registrarlo
    try:
        from .blueprints.admin import bp as admin_bp
        app.register_blueprint(admin_bp)
    except ImportError:
        pass

    # ============ Filtro de plantilla para hora local ============
    @app.template_filter('fecha_local')
    def fecha_local_filter(dt):
        """Convierte datetime UTC a hora local Colombia."""
        if not dt:
            return ''
        return (dt - timedelta(hours=5)).strftime('%d/%m/%Y %H:%M')

    @app.context_processor
    def inject_helpers():
        return {'hora_local': hora_local}

    # ============ Ruta de ping ============
    @app.route('/ping')
    def ping():
        return {'status': 'ok', 'app': 'El Michín', 'modo': app.config['MODO']}

    return app