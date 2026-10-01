# config.py
import os
from dotenv import load_dotenv

# Cargar variables del .env
load_dotenv()


class Config:
    """Configuración base común para todos los modos."""

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'cambia-esto')
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'

    # Modo de la app: 'central' o 'tienda_local'
    MODO = os.getenv('MODO', 'tienda_local')
    TIENDA_ID = int(os.getenv('TIENDA_ID', '1'))

    # Base de datos
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'michin_central')

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
    }

    # URL del servidor central (para sync)
    CENTRAL_URL = os.getenv('CENTRAL_URL', '')

    # Impresora
    IMPRESORA_IP = os.getenv('IMPRESORA_IP', '192.168.0.14')
    IMPRESORA_PUERTO = int(os.getenv('IMPRESORA_PUERTO', '9100'))

    # IA (opcional)
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')

    # Sincronizacion entre tiendas y central
    SYNC_KEY = os.getenv('SYNC_KEY', '')

    # ============ CSRF / Seguridad ============
    # Desactivar chequeo estricto de HTTPS en CSRF (necesario por ProxyFix + Cloudflare)
    WTF_CSRF_SSL_STRICT = False

    # Hosts de confianza para CSRF (deben incluir TODOS los orígenes desde donde se accede)
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:5000',
        'http://127.0.0.1:5000',
        'http://10.2.0.2:5000',
        'http://192.168.1.50:5000',
        'http://192.168.1.51:5000',
        'https://central.elmichin.com',
    ]

    # Cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    # No forzar Secure en cookies porque en localhost no hay HTTPS
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

    # Configuración multi-tienda
    TIENDAS = {
        1: "El Michín Lucero",
        2: "El Michín Centro",
    }

    @property
    def es_central(self):
        return self.MODO == 'central'

    @property
    def es_tienda(self):
        return self.MODO == 'tienda_local'


class DevelopmentConfig(Config):
    DEBUG = True
    FLASK_ENV = 'development'


class ProductionConfig(Config):
    DEBUG = False
    FLASK_ENV = 'production'


# Mapa de configuraciones
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}


def get_config():
    """Devuelve la clase de configuración según FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)