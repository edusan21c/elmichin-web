# wsgi.py
import os
os.environ['TZ'] = 'America/Bogota'  # Zona horaria Colombia (UTC-5)
try:
    import time
    time.tzset()
except AttributeError:
    pass  # Windows no tiene tzset, usamos workaround abajo

from app import create_app
from app.extensions import db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    print("\n" + "=" * 60)
    print("🐱 EL MICHÍN - Servidor Flask")
    print("=" * 60)
    print(f"Modo: {app.config['MODO']}")
    print(f"Tienda ID: {app.config['TIENDA_ID']}")
    print(f"DB: {app.config['DB_NAME']}")
    print(f"URL: http://localhost:5000")
    print("=" * 60 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
