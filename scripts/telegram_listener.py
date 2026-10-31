# scripts/telegram_listener.py
"""Escucha los mensajes de Telegram y responde con datos del sistema."""
import sys
import os
import time
import requests

sys.path.append(r'C:\michin_web')

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.cliente import Cliente

def send_message(app, text):
    token = app.config.get('TELEGRAM_TOKEN', '')
    chat_id = app.config.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=10)
    except Exception as e:
        print(f'Error enviando mensaje: {e}')

def main():
    app = create_app()
    token = app.config.get('TELEGRAM_TOKEN', '')
    
    if not token:
        print("Token de Telegram no configurado.")
        return

    print("🤖 Vigilante escuchando mensajes de Telegram... (Ctrl+C para salir)")
    offset = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=30"
            r = requests.get(url, timeout=35)
            data = r.json()

            if data.get('ok'):
                for update in data['result']:
                    offset = update['update_id'] + 1
                    
                    if 'message' not in update:
                        continue
                        
                    message = update['message']
                    text = message.get('text', '').strip()
                    chat_id_real = message['chat']['id']
                    
                    # Solo responder al chat autorizado
                    chat_id_config = app.config.get('TELEGRAM_CHAT_ID')
                    if str(chat_id_real) != str(chat_id_config):
                        send_message(app, "⛔ No tienes permiso para hablar conmigo.")
                        continue

                    texto_min = text.lower()

                    # ================= COMANDOS =================
                    if texto_min.startswith('/start') or texto_min.startswith('/ayuda'):
                        ayuda = (
                            "🤖 *¡Hola Jean! Soy tu vigilante.*\n\n"
                            "Comandos disponibles:\n"
                            "📊 `/estado` - Reporte rápido de ventas\n"
                            "🔍 `/buscar [producto]` - Buscar stock\n"
                            "💸 `/deudas` - Ver total adeudado\n"
                            "🔄 `/sync` - Ver pendientes de sync"
                        )
                        send_message(app, ayuda)

                    elif texto_min.startswith('/estado'):
                        with app.app_context():
                            from scripts.vigilante import generar_reporte
                            reporte = generar_reporte(app)
                            send_message(app, reporte)

                    elif texto_min.startswith('/buscar'):
                        query = text[7:].strip()
                        if not query:
                            send_message(app, "⚠️ Escribe el nombre del producto. Ejemplo: `/buscar haba`")
                        else:
                            with app.app_context():
                                prod = Producto.query.filter(Producto.nombre.ilike(f'%{query}%')).first()
                                if not prod:
                                    send_message(app, f"❌ No encontré ningún producto con '{query}'.")
                                else:
                                    t1 = ProductoTienda.query.filter_by(producto_id=prod.id, tienda_id=1).first()
                                    t2 = ProductoTienda.query.filter_by(producto_id=prod.id, tienda_id=2).first()
                                    st1 = t1.cantidad if t1 else 0
                                    st2 = t2.cantidad if t2 else 0
                                    p1 = f"${float(t1.precio_venta):,.0f}" if t1 else "N/A"
                                    res = (
                                        f"🔍 *{prod.nombre}*\n"
                                        f"Código: `{prod.codigo_barras}`\n\n"
                                        f"🏪 *Central (T1):* {st1} und. (Venta: {p1})\n"
                                        f"🏪 *Tienda 2:* {st2} und.\n"
                                    )
                                    send_message(app, res)

                    elif texto_min.startswith('/deudas'):
                        with app.app_context():
                            clientes_deuda = db.session.query(
                                db.func.count(Cliente.id),
                                db.func.coalesce(db.func.sum(Cliente.saldo_actual), 0)
                            ).filter(Cliente.saldo_actual > 0.01).first()
                            msg = (
                                f"👥 *Clientes con Deuda*\n"
                                f"Personas: {clientes_deuda[0]}\n"
                                f"Total adeudado: ${float(clientes_deuda[1]):,.0f}"
                            )
                            send_message(app, msg)

                    elif texto_min.startswith('/sync'):
                        with app.app_context():
                            pendientes = ProductoTienda.query.filter_by(sync_estado='pendiente').count()
                            if pendientes > 0:
                                send_message(app, f"🔄 Hay *{pendientes}* productos pendientes por enviar a las tiendas.")
                            else:
                                send_message(app, "✅ Todo está sincronizado. No hay pendientes.")

                    else:
                        send_message(app, "🤔 No entendí ese comando. Escribe `/ayuda` para ver qué puedo hacer.")

        except requests.exceptions.RequestException as e:
            print(f"Error de red: {e}. Reintentando en 5 seg...")
            time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()