import re

file_path = r'C:\michin_web\app\blueprints\facturacion\routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    r"match_unidad = re.findall(r'(\d+)\s*(?:g|gr|ml|l|lt|kg|un|und)\b', nombre_sin_asterisco, re.IGNORECASE)",
    r"match_unidad = re.findall(r'(\d+)\s*(g|gr|ml|l|lt|kg|un|und)\b', nombre_sin_asterisco, re.IGNORECASE)"
)

content = content.replace(
    "num_principal = match_unidad[0]",
    "num_principal = match_unidad[0][0]\n        unidad_principal = match_unidad[0][1].lower()"
)
content = content.replace(
    "num_principal = numeros_base[-1] if numeros_base else None",
    "num_principal = numeros_base[-1] if numeros_base else None\n        unidad_principal = None"
)

old_filter = """    if num_principal:
        query = query.filter(Producto.nombre.ilike(f'%{num_principal}%'))
        
    productos = query.all()"""

new_filter = """    if num_principal:
        query = query.filter(Producto.nombre.ilike(f'%{num_principal}%'))
        
        if unidad_principal:
            if unidad_principal in ['g', 'gr']:
                query = query.filter(or_(
                    Producto.nombre.ilike(f'%{num_principal}g%'),
                    Producto.nombre.ilike(f'%{num_principal} g%'),
                    Producto.nombre.ilike(f'%{num_principal}gr%'),
                    Producto.nombre.ilike(f'%{num_principal} gr%')
                ))
            elif unidad_principal in ['un', 'und']:
                query = query.filter(or_(
                    Producto.nombre.ilike(f'%{num_principal}u%'),
                    Producto.nombre.ilike(f'%{num_principal} u%'),
                    Producto.nombre.ilike(f'%{num_principal}un%'),
                    Producto.nombre.ilike(f'%{num_principal} un%'),
                    Producto.nombre.ilike(f'%{num_principal}und%')
                ))
        
    productos = query.all()"""

content = content.replace(old_filter, new_filter)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("¡Archivo parcheado con exito! La base de datos esta intacta.")
