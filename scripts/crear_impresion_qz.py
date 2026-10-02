# scripts/crear_impresion_qz.py
# Modulo de impresion con QZ Tray (impresora termica desde el navegador).
# Ejecutar UNA VEZ: python scripts\crear_impresion_qz.py

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVOS = {}

# ==================== API PARA GENERAR TICKET ====================
ARCHIVOS['app/blueprints/api/impresion.py'] = '''# app/blueprints/api/impresion.py
from datetime import timedelta
from flask import jsonify, current_app
from flask_login import login_required, current_user
from . import bp
from app.extensions import db
from app.models.factura import Factura, DetalleFactura
from app.models.tienda import Tienda
from app.models.configuracion import Configuracion


def get_config(clave, default=''):
    conf = Configuracion.query.filter_by(clave=clave).first()
    return conf.valor if conf else default


def get_config_tienda(clave, tienda_id, default=''):
    conf = Configuracion.query.filter_by(clave=clave, tienda_id=tienda_id).first()
    return conf.valor if conf else default


@bp.route('/ticket/<int:factura_id>/escpos')
@login_required
def ticket_escpos(factura_id):
    """
    Devuelve el ticket como lista de lineas para enviar a QZ Tray.
    Formato: array de strings, cada uno es una linea del ticket.
    """
    factura = Factura.query.get_or_404(factura_id)
    detalles = DetalleFactura.query.filter_by(factura_id=factura_id).all()
    cliente = factura.cliente
    tienda = factura.tienda

    # Leer configuracion
    negocio_nombre = get_config('negocio_nombre', 'El Michín')
    negocio_nit = get_config('negocio_nit', '')
    negocio_slogan = get_config('negocio_slogan', '')

    # Config por tienda (si no existe, usar global/default)
    tienda_id = factura.tienda_id
    direccion = get_config_tienda('negocio_direccion', tienda_id, '')
    telefono = get_config_tienda('negocio_telefono', tienda_id, '')

    # Fecha local (Colombia = UTC-5)
    fecha_local = factura.fecha_hora - timedelta(hours=5)

    # Construir lineas (ancho tipico 80mm = ~42-48 caracteres)
    W = 42
    lineas = []

    lineas.append(negocio_nombre.upper().center(W))
    if negocio_nit:
        lineas.append(f'NIT: {negocio_nit}'.center(W))
    if direccion:
        lineas.append(direccion[:W].center(W))
    if telefono:
        lineas.append(f'Tel: {telefono}'.center(W))
    lineas.append('=' * W)

    lineas.append(f'Fecha: {fecha_local.strftime("%d/%m/%Y %H:%M")}')
    lineas.append(f'Ticket: {factura.numero_factura}')
    lineas.append(f'Cliente: {(cliente.nombre if cliente else "")[:W-9]}')
    if cliente and cliente.documento:
        lineas.append(f'Doc: {cliente.documento}')
    if factura.usuario:
        lineas.append(f'Atendio: {factura.usuario.nombre[:W-9]}')

    lineas.append('-' * W)
    lineas.append(f'{"Producto":<20} {"Cant":>4} {"P.Unit":>8} {"Total":>8}')
    lineas.append('-' * W)

    for d in detalles:
        nombre = d.producto_nombre[:20]
        cant = str(d.cantidad)
        pu = f'{float(d.precio_unitario or 0):,.0f}'
        sub = f'{float(d.subtotal or 0):,.0f}'
        lineas.append(f'{nombre:<20} {cant:>4} {pu:>8} {sub:>8}')

    lineas.append('-' * W)
    lineas.append(f'{"Subtotal:":>{W-12}} ${float(factura.subtotal or 0):>10,.0f}')
    if factura.recargo_nequi and float(factura.recargo_nequi) > 0:
        lineas.append(f'{"Recargo digital:":>{W-12}} ${float(factura.recargo_nequi):>10,.0f}')
    if factura.recargo_bolsa and float(factura.recargo_bolsa) > 0:
        lineas.append(f'{"Bolsas:":>{W-12}} ${float(factura.recargo_bolsa):>10,.0f}')

    lineas.append('-' * W)
    lineas.append(f'{"TOTAL:":>{W-12}} ${float(factura.total or 0):>10,.0f}')
    lineas.append('-' * W)

    if factura.metodo_pago == 'credito':
        lineas.append(f'Pago: CREDITO')
        lineas.append(f'Saldo pendiente: ${float(factura.saldo_pendiente or 0):,.0f}')
    else:
        lineas.append(f'Pagado: ${float(factura.valor_pagado or 0):,.0f}')
        lineas.append(f'Vueltas: ${float(factura.vueltas or 0):,.0f}')

    lineas.append('=' * W)
    lineas.append('Gracias por su compra'.center(W))
    if negocio_slogan:
        lineas.append(negocio_slogan.center(W))
    lineas.append('@elmichin'.center(W))

    # Config impresora
    impresora_ip = get_config_tienda('impresora_ip', tienda_id, '192.168.0.14')
    impresora_puerto = get_config_tienda('impresora_puerto', tienda_id, '9100')

    return jsonify({
        'lineas': lineas,
        'impresora_ip': impresora_ip,
        'impresora_puerto': int(impresora_puerto) if impresora_puerto else 9100,
    })
'''

# ==================== ACTUALIZAR __init__.py DEL API ====================
ARCHIVOS['app/blueprints/api/__init__.py'] = '''# app/blueprints/api/__init__.py
from flask import Blueprint

bp = Blueprint('api', __name__, url_prefix='/api')

from . import sync       # noqa: E402, F401
from . import impresion  # noqa: E402, F401
'''

# ==================== JAVASCRIPT QZ TRAY ====================
ARCHIVOS['app/static/js/qz-print.js'] = '''// app/static/js/qz-print.js
// Comunicacion con QZ Tray para imprimir tickets en impresora termica.
(function() {
    'use strict';

    const QZ_URL_WEBSOCKET = 'wss://localhost:8182';
    const QZ_URL_SECURE = 'wss://localhost:8182';
    const QZ_URL_INSECURE = 'ws://localhost:8182';

    let qzConectado = false;
    let qzIntentando = false;

    // ==================== CONEXION ====================
    function conectarQZ() {
        if (qzConectado || qzIntentando) return Promise.resolve(qzConectado);
        qzIntentando = true;

        return new Promise((resolve) => {
            try {
                // QZ Tray 2.2+ usa HTTPS/wss por defecto
                qz.security.setCertificatePromise(function(resolve, reject) {
                    resolve();
                });
                qz.security.setSignaturePromise(function(toSign) {
                    return function(resolve) {
                        resolve();
                    };
                });

                qz.websocket.connect({host: 'localhost', port: 8182, usingSecure: true})
                    .then(() => {
                        qzConectado = true;
                        qzIntentando = false;
                        console.log('QZ Tray conectado');
                        resolve(true);
                    })
                    .catch(err => {
                        console.warn('No se pudo conectar a QZ Tray:', err);
                        qzIntentando = false;
                        resolve(false);
                    });
            } catch (e) {
                qzIntentando = false;
                resolve(false);
            }
        });
    }

    // ==================== IMPRIMIR ====================
    async function imprimirTicket(facturaId, forzarIp, forzarPuerto) {
        const conectado = await conectarQZ();
        if (!conectado) {
            mostrarAlerta('QZ Tray no esta corriendo. Abrelo y vuelve a intentar.', 'warning');
            return false;
        }

        try {
            // 1. Obtener las lineas del ticket desde el servidor
            const r = await fetch(`/api/ticket/${facturaId}/escpos`);
            if (!r.ok) {
                throw new Error('Error obteniendo ticket: ' + r.status);
            }
            const data = await r.json();

            // 2. Configurar impresora
            const ip = forzarIp || data.impresora_ip || '192.168.0.14';
            const puerto = forzarPuerto || data.impresora_puerto || 9100;

            const printer = await qz.printers.find();
            let config;
            if (printer && printer.length > 0) {
                // Buscar impresora que contenga la IP o usar la primera
                config = qz.configs.create(printer[0]);
            } else {
                // Fallback: usar IP directa
                config = qz.configs.create({
                    host: ip,
                    port: puerto,
                    encoding: 'CP850',
                });
            }

            // 3. Convertir lineas a bytes ESC/POS
            const contenido = data.lineas.join('\\n') + '\\n\\n\\n\\n';
            const dataToPrint = [{
                type: 'raw',
                format: 'plain',
                data: contenido,
                options: { encoding: 'CP850' }
            }];

            // 4. Enviar a QZ Tray
            await qz.print(config, dataToPrint);
            mostrarAlerta('Ticket enviado a impresora', 'success');
            return true;

        } catch (e) {
            console.error('Error imprimiendo:', e);
            mostrarAlerta('Error al imprimir: ' + e.message, 'danger');
            return false;
        }
    }

    // ==================== ALERTA FLOTANTE ====================
    function mostrarAlerta(mensaje, tipo) {
        const color = tipo === 'danger' ? 'danger' :
                      tipo === 'warning' ? 'warning' :
                      tipo === 'success' ? 'success' : 'info';

        const div = document.createElement('div');
        div.className = `alert alert-${color} position-fixed top-0 start-50 translate-middle-x mt-3 shadow`;
        div.style.zIndex = '9999';
        div.style.minWidth = '320px';
        div.innerHTML = `<i class="bi bi-info-circle"></i> ${mensaje}`;
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 3000);
    }

    // ==================== EXPONER GLOBAL ====================
    window.MichinPrint = {
        imprimirTicket: imprimirTicket,
        conectar: conectarQZ,
    };

    // Auto-conectar cuando carga la pagina
    document.addEventListener('DOMContentLoaded', () => {
        conectarQZ().then(ok => {
            if (ok) {
                console.log('Listo para imprimir con QZ Tray');
            } else {
                console.warn('QZ Tray no disponible. Los tickets se pueden imprimir con Ctrl+P.');
            }
        });
    });

})();
'''

# ==================== ACTUALIZAR TICKET HTML ====================
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

                <div id="qz-status" class="alert alert-secondary small py-2">
                    <i class="bi bi-hourglass-split"></i> Verificando impresora...
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
                    <button id="btn-imprimir-qz" type="button" class="btn btn-success btn-lg" data-factura-id="{{ factura.id }}">
                        <i class="bi bi-printer-fill"></i> Imprimir en térmica (QZ Tray)
                    </button>
                    <a href="{{ url_for('facturacion.nueva') }}" class="btn btn-primary btn-lg">
                        <i class="bi bi-plus-circle"></i> Nueva venta
                    </a>
                    <button onclick="window.print()" class="btn btn-outline-secondary btn-sm">
                        <i class="bi bi-printer"></i> Imprimir con Ctrl+P
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>

<script src="{{ url_for('static', filename='js/qz-print.js') }}"></script>
<script>
    document.addEventListener('DOMContentLoaded', () => {
        const btn = document.getElementById('btn-imprimir-qz');
        const status = document.getElementById('qz-status');
        const facturaId = btn.dataset.facturaId;

        // Actualizar estado de QZ
        setTimeout(() => {
            if (window.MichinPrint) {
                window.MichinPrint.conectar().then(ok => {
                    if (ok) {
                        status.className = 'alert alert-success small py-2';
                        status.innerHTML = '<i class="bi bi-check-circle"></i> QZ Tray conectado. Listo para imprimir.';
                        btn.disabled = false;
                    } else {
                        status.className = 'alert alert-warning small py-2';
                        status.innerHTML = '<i class="bi bi-exclamation-triangle"></i> QZ Tray no esta corriendo. Usa Ctrl+P o abre QZ Tray.';
                        btn.disabled = true;
                    }
                });
            }
        }, 1000);

        // Boton imprimir
        btn.addEventListener('click', async () => {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Imprimiendo...';

            const ok = await window.MichinPrint.imprimirTicket(facturaId);

            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-printer-fill"></i> Imprimir en térmica (QZ Tray)';
        });
    });
</script>
{% endblock %}
'''


def main():
    print(f'Creando modulo de impresion QZ en: {RAIZ}')
    print('-' * 60)
    for rel_path, contenido in ARCHIVOS.items():
        ruta = os.path.join(RAIZ, *rel_path.split('/'))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        print(f'  OK  {rel_path}')
    print('-' * 60)
    print(f'Listo: {len(ARCHIVOS)} archivos creados.')
    print()
    print('PROXIMOS PASOS:')
    print('  1. Verifica que QZ Tray este instalado y corriendo')
    print('  2. Reinicia el servicio Flask')
    print('  3. Abre un ticket y prueba el boton verde')


if __name__ == '__main__':
    main()