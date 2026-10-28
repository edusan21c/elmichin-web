import sys
sys.path.append(r'C:\michin_web')
from app import create_app
from app.extensions import db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    print("--- TABLAS QUE ESTAN CONECTADAS A LOS PRODUCTOS ---")
    
    for table_name in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table_name):
            # Buscamos las tablas que apunten a 'producto' o 'productos'
            if 'producto' in fk['referred_table'].lower():
                print(f"La tabla '{table_name}' usa el producto en la columna '{fk['constrained_columns'][0]}'")