# app/__init__.py
from flask import Flask
from .extensions import db, migrate, login_manager, csrf
from config import get_config


def create_app(config_class=None):
    """Factory de la aplicación Flask."""
    app = Flask(__name__)
    
    # Cargar configuración
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)
    
    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Importar modelos (para que Alembic los detecte)
    from .models import usuario, tienda, producto, cliente, factura
    from .models import pago, venta, borrador, configuracion, sync_log
    
    # Configurar login manager
    from .models.usuario import Usuario
    
    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))
    
    # Registrar blueprints
    from .blueprints.auth import bp as auth_bp
    from .blueprints.dashboard import bp as dashboard_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    
    # Página de inicio temporal (hasta que tengamos template)
    @app.route('/ping')
    def ping():
        return {'status': 'ok', 'app': 'El Michín', 'modo': app.config['MODO']}
    
    return app