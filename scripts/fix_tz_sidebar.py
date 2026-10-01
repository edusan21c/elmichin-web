# scripts/fix_tz_sidebar.py
# Arregla zona horaria (UTC-5 Colombia) + actualiza sidebar.
# Ejecutar: python scripts\fix_tz_sidebar.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== FIX TZ EN WSGI ====================
ARCHIVOS['wsgi.py'] = '''# wsgi.py
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

    print("\\n" + "=" * 60)
    print("🐱 EL MICHÍN - Servidor Flask")
    print("=" * 60)
    print(f"Modo: {app.config['MODO']}")
    print(f"Tienda ID: {app.config['TIENDA_ID']}")
    print(f"DB: {app.config['DB_NAME']}")
    print(f"URL: http://localhost:5000")
    print("=" * 60 + "\\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
'''

# ==================== FIX TZ EN APP INIT ====================
ARCHIVOS['app/__init__.py'] = '''# app/__init__.py
from datetime import datetime, timedelta
from flask import Flask
from .extensions import db, migrate, login_manager, csrf
from config import get_config


def hora_local():
    """Devuelve la hora actual en zona horaria de Colombia (UTC-5)."""
    return datetime.utcnow() - timedelta(hours=5)


def create_app(config_class=None):
    """Factory de la aplicación Flask."""
    app = Flask(__name__)

    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Importar modelos
    from .models import usuario, tienda, producto, cliente, factura
    from .models import pago, venta, borrador, configuracion, sync_log

    from .models.usuario import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # Registrar blueprints
    from .blueprints.auth import bp as auth_bp
    from .blueprints.dashboard import bp as dashboard_bp
    from .blueprints.inventario import bp as inventario_bp
    from .blueprints.facturacion import bp as facturacion_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(facturacion_bp)

    # Filtro de plantilla para hora local
    @app.template_filter('fecha_local')
    def fecha_local_filter(dt):
        """Convierte datetime UTC a hora local Colombia."""
        if not dt:
            return ''
        return (dt - timedelta(hours=5)).strftime('%d/%m/%Y %H:%M')

    @app.context_processor
    def inject_helpers():
        return {'hora_local': hora_local}

    # Ping
    @app.route('/ping')
    def ping():
        return {'status': 'ok', 'app': 'El Michín', 'modo': app.config['MODO']}

    return app
'''

# ==================== FIX TZ EN SERVICE ====================
ARCHIVOS['app/services/facturacion_service.py'] = '''# app/services/facturacion_service.py
"""Logica de negocio para facturacion."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.cliente import Cliente
from app.models.factura import Factura, DetalleFactura
from app.models.venta import Venta


def hora_local():
    return datetime.utcnow() - timedelta(hours=5)


def redondear(v):
    return Decimal(str(v or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def generar_numero_factura(tienda_id):
    """Genera numero unico: FAC-T{tienda}-0001."""
    ultima = (Factura.query
              .filter_by(tienda_id=tienda_id)
              .order_by(Factura.id.desc())
              .first())
    if ultima:
        try:
            num = int(ultima.numero_factura.split('-')[-1])
            siguiente = num + 1
        except (ValueError, IndexError):
            siguiente = 1
    else:
        siguiente = 1
    return f'FAC-T{tienda_id}-{siguiente:04d}'


def obtener_o_crear_cliente(tienda_id, nombre, documento='', direccion='', telefono='', email=''):
    """Busca cliente por nombre+documento o lo crea."""
    nombre = (nombre or '').strip()
    documento = (documento or '').strip()

    query = Cliente.query.filter_by(tienda_id=tienda_id, nombre=nombre)
    if documento:
        query = query.filter_by(documento=documento)
    cliente = query.first()

    if cliente:
        if direccion and direccion != cliente.direccion:
            cliente.direccion = direccion
        if telefono and telefono != cliente.telefono:
            cliente.telefono = telefono
        if email and email != cliente.email:
            cliente.email = email
        return cliente

    cliente = Cliente(
        tienda_id=tienda_id,
        nombre=nombre,
        documento=documento or None,
        direccion=direccion or None,
        telefono=telefono or None,
        email=email or None,
        saldo_actual=Decimal('0'),
    )
    db.session.add(cliente)
    db.session.flush()
    return cliente


def crear_factura_completa(
    tienda_id,
    usuario_id,
    cliente_data,
    carrito,
    metodo_pago,
    recargo_porcentaje=Decimal('0.4'),
    bolsas_cantidad=0,
    valor_bolsa=Decimal('100'),
    valor_pagado=Decimal('0'),
):
    """Crea factura completa con validaciones y actualizaciones."""
    if not carrito:
        return None, 'El carrito esta vacio'

    items_procesados = []
    subtotal = Decimal('0')

    for item in carrito:
        producto_id = int(item['producto_id'])
        cantidad = int(item['cantidad'])
        if cantidad <= 0:
            return None, f'Cantidad invalida'

        producto = Producto.query.get(producto_id)
        if not producto:
            return None, f'Producto no encontrado'

        pres = ProductoTienda.query.filter_by(
            producto_id=producto_id, tienda_id=tienda_id
        ).first()
        if not pres:
            return None, f'Producto "{producto.nombre}" no disponible'

        if pres.cantidad < cantidad:
            return None, f'Stock insuficiente para "{producto.nombre}" (disponible: {pres.cantidad})'

        precio_unitario = redondear(item.get('precio_unitario') or pres.calcular_precio(cantidad))
        item_subtotal = redondear(precio_unitario * cantidad)
        subtotal += item_subtotal

        items_procesados.append({
            'producto': producto,
            'presentacion': pres,
            'cantidad': cantidad,
            'precio_unitario': precio_unitario,
            'subtotal': item_subtotal,
        })

    recargo = Decimal('0')
    if metodo_pago in ('nequi', 'daviplata'):
        recargo = redondear(subtotal * (Decimal(str(recargo_porcentaje)) / Decimal('100')))

    total_bolsas = redondear(Decimal(str(bolsas_cantidad)) * Decimal(str(valor_bolsa)))
    total_final = redondear(subtotal + recargo + total_bolsas)

    if metodo_pago == 'credito':
        valor_pagado = Decimal('0')
        vueltas = Decimal('0')
        saldo_pendiente = total_final
    else:
        valor_pagado = redondear(valor_pagado)
        if valor_pagado < total_final - Decimal('0.01'):
            return None, f'Faltan ${total_final - valor_pagado:.0f}'
        vueltas = redondear(valor_pagado - total_final)
        saldo_pendiente = Decimal('0')

    cliente = obtener_o_crear_cliente(
        tienda_id,
        cliente_data.get('nombre', 'Cliente ocasional'),
        cliente_data.get('documento', ''),
        cliente_data.get('direccion', ''),
        cliente_data.get('telefono', ''),
        cliente_data.get('email', ''),
    )

    numero = generar_numero_factura(tienda_id)
    tipo_pago = 'credito' if saldo_pendiente > 0 else 'contado'
    estado_credito = 'pendiente' if saldo_pendiente > 0 else 'pagado'

    factura = Factura(
        numero_factura=numero,
        tienda_id=tienda_id,
        cliente_id=cliente.id,
        usuario_id=usuario_id,
        subtotal=subtotal,
        total=total_final,
        metodo_pago=metodo_pago,
        recargo_nequi=recargo,
        recargo_bolsa=total_bolsas,
        valor_pagado=valor_pagado,
        vueltas=vueltas,
        tipo_pago=tipo_pago,
        estado_credito=estado_credito,
        saldo_pendiente=saldo_pendiente,
    )
    db.session.add(factura)
    db.session.flush()

    for item in items_procesados:
        detalle = DetalleFactura(
            factura_id=factura.id,
            producto_id=item['producto'].id,
            producto_nombre=item['producto'].nombre,
            cantidad=item['cantidad'],
            precio_unitario=item['precio_unitario'],
            subtotal=item['subtotal'],
        )
        db.session.add(detalle)

        venta = Venta(
            tienda_id=tienda_id,
            producto_id=item['producto'].id,
            cantidad=item['cantidad'],
            precio_unitario=item['precio_unitario'],
            total=item['subtotal'],
        )
        db.session.add(venta)

        item['presentacion'].cantidad = item['presentacion'].cantidad - item['cantidad']

    if saldo_pendiente > 0:
        cliente.saldo_actual = redondear(Decimal(str(cliente.saldo_actual or 0)) + saldo_pendiente)

    db.session.commit()
    return factura.id, None
'''

# ==================== SIDEBAR CON FACTURACION ACTIVA ====================
ARCHIVOS['app/templates/layout/sidebar.html'] = '''<nav class="col-md-3 col-lg-2 d-md-block bg-light sidebar border-end" style="min-height: calc(100vh - 56px);">
    <div class="position-sticky pt-3">
        <ul class="nav flex-column">
            <li class="nav-item">
                <a class="nav-link {% if request.endpoint == 'dashboard.index' %}active{% endif %}"
                   href="{{ url_for('dashboard.index') }}">
                    <i class="bi bi-house-door"></i> Inicio
                </a>
            </li>

            {% if current_user.rol in ('admin', 'programador') %}
            <li class="nav-item">
                <a class="nav-link {% if request.blueprint == 'inventario' %}active{% endif %}"
                   href="{{ url_for('inventario.lista') }}">
                    <i class="bi bi-box-seam"></i> Inventario
                </a>
            </li>
            {% endif %}

            {% if current_user.rol in ('admin', 'programador', 'operario') %}
            <li class="nav-item">
                <a class="nav-link {% if request.blueprint == 'facturacion' %}active{% endif %}"
                   href="{{ url_for('facturacion.nueva') }}">
                    <i class="bi bi-receipt"></i> Facturación
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-lightning-charge"></i> Venta Rápida
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-graph-up"></i> Reportes
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            {% endif %}

            {% if current_user.rol in ('admin', 'programador') %}
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-bar-chart"></i> Estadísticas
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            {% endif %}

            {% if current_user.rol == 'programador' %}
            <li class="nav-item mt-3">
                <small class="text-muted ps-3">ADMINISTRACIÓN</small>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-people"></i> Usuarios
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link disabled" href="#">
                    <i class="bi bi-gear"></i> Configuración
                    <small class="text-muted">(pronto)</small>
                </a>
            </li>
            {% endif %}
        </ul>
    </div>
</nav>
'''

# ==================== FIX TICKET (hora local) ====================
ARCHIVOS['app/templates/facturacion/ticket.html'] = '''{% extends 'base.html' %}
{% block titulo %}Ticket {{ factura.numero_factura }}{% endblock %}

{% block contenido %}
<div class="row justify-content-center">
    <div class="col-md-8 col-lg-6">
        <div class="card shadow">
            <div class="card-body text-center">
                <div class="fs-1">🐱</div>
                <h4 class="fw-bold mb-0">EL MICHÍN DULCERÍA</h4>
                <p class="text-muted small mb-3">{{ factura.tienda.nombre }}</p>

                <div class="bg-light p-3 rounded mb-3">
                    <div class="text-success">
                        <i class="bi bi-check-circle fs-1"></i>
                    </div>
                    <h5 class="mt-2 mb-0">Venta registrada</h5>
                    <div class="text-muted small">Ticket {{ factura.numero_factura }}</div>
                </div>

                <table class="table table-sm text-start">
                    <tr><th>Cliente:</th><td>{{ cliente.nombre }}</td></tr>
                    {% if cliente.documento %}
                    <tr><th>Documento:</th><td>{{ cliente.documento }}</td></tr>
                    {% endif %}
                    <tr><th>Fecha:</th><td>{{ factura.fecha_hora | fecha_local }}</td></tr>
                    <tr><th>Método:</th><td>{{ factura.metodo_pago | upper }}</td></tr>
                </table>

                <table class="table table-sm">
                    <thead class="table-light">
                        <tr>
                            <th>Producto</th>
                            <th class="text-center">Cant</th>
                            <th class="text-end">P. Unit</th>
                            <th class="text-end">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for d in detalles %}
                        <tr>
                            <td>{{ d.producto_nombre }}</td>
                            <td class="text-center">{{ d.cantidad }}</td>
                            <td class="text-end">${{ "{:,.0f}".format(d.precio_unitario) }}</td>
                            <td class="text-end">${{ "{:,.0f}".format(d.subtotal) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                    <tfoot>
                        <tr>
                            <th colspan="3" class="text-end">Subtotal</th>
                            <th class="text-end">${{ "{:,.0f}".format(factura.subtotal) }}</th>
                        </tr>
                        {% if factura.recargo_nequi > 0 %}
                        <tr>
                            <td colspan="3" class="text-end">Recargo digital</td>
                            <td class="text-end">${{ "{:,.0f}".format(factura.recargo_nequi) }}</td>
                        </tr>
                        {% endif %}
                        {% if factura.recargo_bolsa > 0 %}
                        <tr>
                            <td colspan="3" class="text-end">Bolsas</td>
                            <td class="text-end">${{ "{:,.0f}".format(factura.recargo_bolsa) }}</td>
                        </tr>
                        {% endif %}
                        <tr class="table-success">
                            <th colspan="3" class="text-end">TOTAL</th>
                            <th class="text-end">${{ "{:,.0f}".format(factura.total) }}</th>
                        </tr>
                        {% if factura.metodo_pago == 'credito' %}
                        <tr class="table-warning">
                            <th colspan="3" class="text-end">Saldo pendiente</th>
                            <th class="text-end">${{ "{:,.0f}".format(factura.saldo_pendiente) }}</th>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="3" class="text-end">Pagado</td>
                            <td class="text-end">${{ "{:,.0f}".format(factura.valor_pagado) }}</td>
                        </tr>
                        <tr>
                            <td colspan="3" class="text-end">Vueltas</td>
                            <td class="text-end">${{ "{:,.0f}".format(factura.vueltas) }}</td>
                        </tr>
                        {% endif %}
                    </tfoot>
                </table>

                <div class="d-grid gap-2 mt-4">
                    <a href="{{ url_for('facturacion.nueva') }}" class="btn btn-primary btn-lg">
                        <i class="bi bi-plus-circle"></i> Nueva venta
                    </a>
                    <button onclick="window.print()" class="btn btn-outline-secondary">
                        <i class="bi bi-printer"></i> Imprimir
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''


def main():
    print(f'Aplicando cambios en: {RAIZ}')
    print('-' * 60)
    for rel_path, contenido in ARCHIVOS.items():
        ruta = os.path.join(RAIZ, *rel_path.split('/'))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f'  OK  {rel_path}')
    print('-' * 60)
    print(f'Listo: {len(ARCHIVOS)} archivos actualizados.')


if __name__ == '__main__':
    main()