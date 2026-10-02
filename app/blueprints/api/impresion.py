# app/blueprints/api/impresion.py
from datetime import timedelta
from flask import jsonify, request
from flask_login import login_required
from . import bp
from app.extensions import db
from app.models.factura import Factura, DetalleFactura
from app.models.configuracion import Configuracion
from app.services import impresion_service


def get_config(clave, default=''):
    conf = Configuracion.query.filter_by(clave=clave).filter(
        Configuracion.tienda_id.is_(None)
    ).first()
    return conf.valor if conf else default


def get_config_tienda(clave, tienda_id, default=''):
    conf = Configuracion.query.filter_by(clave=clave, tienda_id=tienda_id).first()
    return conf.valor if conf else default


def cargar_config_global():
    return {
        'negocio_nombre': get_config('negocio_nombre', 'El Michín'),
        'negocio_nit': get_config('negocio_nit', ''),
        'negocio_slogan': get_config('negocio_slogan', ''),
    }


def cargar_config_tienda(tienda_id):
    return {
        'negocio_direccion': get_config_tienda('negocio_direccion', tienda_id, ''),
        'negocio_telefono': get_config_tienda('negocio_telefono', tienda_id, ''),
        'impresora_ip': get_config_tienda('impresora_ip', tienda_id, '192.168.0.14'),
        'impresora_puerto': get_config_tienda('impresora_puerto', tienda_id, '9100'),
    }


@bp.route('/ticket/<int:factura_id>/imprimir', methods=['POST'])
@login_required
def imprimir_ticket(factura_id):
    """Imprime el ticket directamente en la impresora termica via socket."""
    factura = Factura.query.get_or_404(factura_id)
    detalles = DetalleFactura.query.filter_by(factura_id=factura_id).all()
    cliente = factura.cliente
    tienda = factura.tienda

    config = cargar_config_global()
    config_tienda = cargar_config_tienda(factura.tienda_id)

    # Generar bytes ESC/POS
    datos = impresion_service.generar_ticket_escpos(
        factura, detalles, cliente, tienda, config, config_tienda
    )

    # Enviar a impresora
    exito, mensaje = impresion_service.enviar_a_impresora(
        config_tienda['impresora_ip'],
        config_tienda['impresora_puerto'],
        datos,
    )

    return jsonify({
        'ok': exito,
        'mensaje': mensaje,
        'bytes_enviados': len(datos),
    })


@bp.route('/ticket/<int:factura_id>/test', methods=['POST'])
@login_required
def test_impresora(factura_id):
    """Test rapido de conexion (sin imprimir contenido)."""
    factura = Factura.query.get_or_404(factura_id)
    config_tienda = cargar_config_tienda(factura.tienda_id)

    # Enviar solo un init + test
    datos = impresion_service.CMD_INIT + b'\n'
    datos += 'TEST DE IMPRESION OK\n\n\n'.encode('cp850')
    datos += impresion_service.CMD_CUT

    exito, mensaje = impresion_service.enviar_a_impresora(
        config_tienda['impresora_ip'],
        config_tienda['impresora_puerto'],
        datos,
    )

    return jsonify({'ok': exito, 'mensaje': mensaje})