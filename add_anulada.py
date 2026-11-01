from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE facturas ADD COLUMN anulada BOOLEAN DEFAULT FALSE;"))
        db.session.commit()
        print("EXITO: Columna 'anulada' agregada a la base de datos.")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("La columna 'anulada' ya existe, todo bien.")
        else:
            print("Error:", e)
