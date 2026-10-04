# app/services/impresion_service.py
"""Servicio de impresion ESC/POS directa por socket TCP."""
import socket
from datetime import timedelta


# ==================== COMANDOS ESC/POS ====================
ESC = b'\x1b'
GS = b'\x1d'

CMD_INIT = ESC + b'@'                    # Inicializar
CMD_CUT = GS + b'V' + b'\x42' + b'\x00'  # Cortar con feed
CMD_FEED = b'\n\n\n'
CMD_BEEP = ESC + b'B' + b'\x03' + b'\x02'  # Beep x3

ALIGN_LEFT = ESC + b'a' + b'\x00'
ALIGN_CENTER = ESC + b'a' + b'\x01'
ALIGN_RIGHT = ESC + b'a' + b'\x02'

BOLD_ON = ESC + b'E' + b'\x01'
BOLD_OFF = ESC + b'E' + b'\x00'

SIZE_NORMAL = GS + b'!' + b'\x00'
SIZE_DOUBLE = GS + b'!' + b'\x11'       # Doble alto y ancho
SIZE_BIG = GS + b'!' + b'\x22'          # Triple


def _texto(s):
    """Convierte string a bytes CP850 (compatible con la impresora).
    Reemplaza caracteres problemáticos que la impresora muestra mal."""
    if isinstance(s, bytes):
        return s
    # La impresora muestra mal la Í mayúscula → la cambiamos por I
    reemplazos = {
        'Í': 'I', 'Á': 'A', 'É': 'E', 'Ó': 'O', 'Ú': 'U',
        'Ü': 'U', 'Ñ': 'N',
    }
    for viejo, nuevo in reemplazos.items():
        s = s.replace(viejo, nuevo)
    return s.encode('cp850', errors='replace')


def generar_ticket_escpos(factura, detalles, cliente, tienda, config, config_tienda):
    """
    Genera los bytes ESC/POS del ticket.
    Retorna bytes listos para enviar por socket.
    """
    W = 42  # Ancho de caracteres por linea
    partes = []

    # Inicializar
    partes.append(CMD_INIT)

    # Encabezado centrado
    partes.append(ALIGN_CENTER)
    partes.append(BOLD_ON)
    partes.append(SIZE_DOUBLE)
    partes.append(_texto(config.get('negocio_nombre', 'El Michin').upper()))
    partes.append(b'\n')
    partes.append(SIZE_NORMAL)
    partes.append(BOLD_OFF)

    nit = config.get('negocio_nit', '')
    if nit:
        partes.append(_texto(f'NIT: {nit}'))
        partes.append(b'\n')

    direccion = config_tienda.get('negocio_direccion', '')
    if direccion:
        partes.append(_texto(direccion[:W]))
        partes.append(b'\n')

    telefono = config_tienda.get('negocio_telefono', '')
    if telefono:
        partes.append(_texto(f'Tel: {telefono}'))
        partes.append(b'\n')

    partes.append(_texto('=' * W))
    partes.append(b'\n')

    # Info factura
    partes.append(ALIGN_LEFT)
    fecha_local = factura.fecha_hora - timedelta(hours=5)
    partes.append(_texto(f'Fecha: {fecha_local.strftime("%d/%m/%Y %H:%M")}'))
    partes.append(b'\n')
    partes.append(_texto(f'Ticket: {factura.numero_factura}'))
    partes.append(b'\n')
    partes.append(_texto(f'Cliente: {(cliente.nombre if cliente else "")[:W-9]}'))
    partes.append(b'\n')
    if cliente and cliente.documento:
        partes.append(_texto(f'Doc: {cliente.documento}'))
        partes.append(b'\n')
    if factura.usuario:
        partes.append(_texto(f'Atendio: {factura.usuario.nombre[:W-9]}'))
        partes.append(b'\n')

    partes.append(_texto('-' * W))
    partes.append(b'\n')

    # Cabecera productos (con negrita)
    partes.append(BOLD_ON)
    partes.append(_texto(f'{"Producto":<20} {"Cant":>4} {"P.Unit":>8} {"Total":>8}'))
    partes.append(b'\n')
    partes.append(BOLD_OFF)
    partes.append(_texto('-' * W))
    partes.append(b'\n')

    # Detalles
    for d in detalles:
        nombre = d.producto_nombre[:20]
        cant = str(d.cantidad)
        pu = f'{float(d.precio_unitario or 0):,.0f}'
        sub = f'{float(d.subtotal or 0):,.0f}'
        partes.append(_texto(f'{nombre:<20} {cant:>4} {pu:>8} {sub:>8}'))
        partes.append(b'\n')

    partes.append(_texto('-' * W))
    partes.append(b'\n')

    # Totales
    partes.append(_texto(f'{"Subtotal:":>{W-12}} ${float(factura.subtotal or 0):>10,.0f}'))
    partes.append(b'\n')

    if factura.recargo_nequi and float(factura.recargo_nequi) > 0:
        partes.append(_texto(f'{"Recargo digital:":>{W-12}} ${float(factura.recargo_nequi):>10,.0f}'))
        partes.append(b'\n')
    if factura.recargo_bolsa and float(factura.recargo_bolsa) > 0:
        partes.append(_texto(f'{"Bolsas:":>{W-12}} ${float(factura.recargo_bolsa):>10,.0f}'))
        partes.append(b'\n')

    partes.append(_texto('-' * W))
    partes.append(b'\n')

    # Total en grande
    partes.append(BOLD_ON)
    partes.append(SIZE_DOUBLE)
    partes.append(ALIGN_CENTER)
    partes.append(_texto(f'TOTAL: ${float(factura.total or 0):,.0f}'))
    partes.append(b'\n')
    partes.append(SIZE_NORMAL)
    partes.append(BOLD_OFF)
    partes.append(ALIGN_LEFT)

    # Pago
    if factura.metodo_pago == 'credito':
        partes.append(_texto('Pago: CREDITO'))
        partes.append(b'\n')
        partes.append(_texto(f'Saldo pendiente: ${float(factura.saldo_pendiente or 0):,.0f}'))
        partes.append(b'\n')
    else:
        partes.append(_texto(f'Pagado: ${float(factura.valor_pagado or 0):,.0f}'))
        partes.append(b'\n')
        partes.append(_texto(f'Vueltas: ${float(factura.vueltas or 0):,.0f}'))
        partes.append(b'\n')

    partes.append(_texto('=' * W))
    partes.append(b'\n')

    # Pie de pagina
    partes.append(ALIGN_CENTER)
    partes.append(_texto('Gracias por su compra'))
    partes.append(b'\n')
    slogan = config.get('negocio_slogan', '')
    if slogan:
        partes.append(_texto(slogan[:W]))
        partes.append(b'\n')
    partes.append(_texto('@elmichin'))
    partes.append(b'\n')

    # Disclaimer legal
    partes.append(_texto('No se aceptan reclamos sin factura'))
    partes.append(b'\n')

    # Feed final + corte + beep
    partes.append(CMD_FEED)
    partes.append(CMD_BEEP)
    partes.append(CMD_CUT)

    return b''.join(partes)


def enviar_a_impresora(ip, puerto, datos):
    """
    Envia bytes a la impresora por socket TCP.
    Retorna (exito, mensaje).
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, int(puerto)))
        sock.sendall(datos)
        sock.close()
        return True, f'Ticket enviado a {ip}:{puerto}'
    except socket.timeout:
        return False, f'Timeout conectando a {ip}:{puerto}. Verifica la IP.'
    except ConnectionRefusedError:
        return False, f'Conexion rechazada por {ip}:{puerto}. Impresora apagada?'
    except socket.gaierror:
        return False, f'IP invalida: {ip}'
    except Exception as e:
        return False, f'Error: {str(e)}'