# scripts/vigilante.py
"""Vigilante del Sistema: Envia un reporte completo a Telegram."""
import sys
import os
from datetime import datetime, timedelta

# Asegurarnos de que encuentra la carpeta raíz
sys.path.append(r'C:\michin_web')

from app import create_app
from app.extensions import db
from app.models.producto import Producto, ProductoTienda
from app.models.factura import Factura
from app.models.cliente import Cliente
from app.models.tienda import Tienda

import requests

def enviar_telegram(app, mensaje):
    token = app.config.get('TELEGRAM_TOKEN', '')
    chat_id = app.config.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        print('Telegram no configurado en el sistema.')
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, json={
            'chat_id': chat_id,
            'text': mensaje,
            'parse_mode': 'Markdown'
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f'Error al conectar con Telegram: {e}')
        return False


def generar_reporte(app):
    with app.app_context():
        # Hora local y UTC (para las consultas a la base de datos)
        ahora_utc = datetime.utcnow()
        ahora_local = ahora_utc - timedelta(hours=5)
        inicio_hoy_local = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
        inicio_hoy_utc = inicio_hoy_local + timedelta(hours=5)
        inicio_mes_local = inicio_hoy_local.replace(day=1)
        inicio_mes_utc = inicio_mes_local + timedelta(hours=5)

        tiendas = Tienda.query.filter_by(activa=True).all()

        lineas = []
        lineas.append("🤖 *REPORTE DEL SISTEMA EL MICHIN*")
        lineas.append(f"📅 {ahora_local.strftime('%d/%m/%Y %H:%M')}")
        lineas.append("")

        # ---- Reporte por tienda ----
        for tienda in tiendas:
            total_prod = ProductoTienda.query.filter_by(tienda_id=tienda.id).count()
            
            stock_bajo = ProductoTienda.query.filter(
                ProductoTienda.tienda_id == tienda.id,
                ProductoTienda.cantidad > 0,
                ProductoTienda.cantidad <= 5
            ).count()
            
            agotados = ProductoTienda.query.filter(
                ProductoTienda.tienda_id == tienda.id,
                ProductoTienda.cantidad <= 0
            ).count()
            
            ventas_hoy = db.session.query(
                db.func.count(Factura.id),
                db.func.coalesce(db.func.sum(Factura.total), 0)
            ).filter(
                Factura.tienda_id == tienda.id,
                Factura.fecha_hora >= inicio_hoy_utc
            ).first()
            
            num_facturas = ventas_hoy[0] or 0
            monto_hoy = float(ventas_hoy[1] or 0)
            
            ventas_mes = db.session.query(
                db.func.coalesce(db.func.sum(Factura.total), 0)
            ).filter(
                Factura.tienda_id == tienda.id,
                Factura.fecha_hora >= inicio_mes_utc
            ).scalar() or 0
            
            lineas.append(f"🏪 *{tienda.nombre}*")
            lineas.append(f"   📦 Productos: {total_prod}")
            lineas.append(f"   ⚠️ Stock bajo: {stock_bajo}")
            lineas.append(f"   ❌ Agotados: {agotados}")
            lineas.append(f"   💰 Ventas hoy: ${monto_hoy:,.0f} ({num_facturas} fact.)")
            lineas.append(f"   📊 Ventas mes: ${float(ventas_mes):,.0f}")
            lineas.append("")

        # ---- Estado de las fotos ----
        con_foto = Producto.query.filter(Producto.imagen.isnot(None)).count()
        sin_foto = Producto.query.filter(Producto.imagen.is_(None)).count()
        total_prod_central = con_foto + sin_foto
        porcentaje = (con_foto / total_prod_central * 100) if total_prod_central > 0 else 0

        lineas.append(f"📸 *Fotos del Catálogo Central*")
        lineas.append(f"   ✅ Con foto: {con_foto}/{total_prod_central} ({porcentaje:.1f}%)")
        lineas.append(f"   ❌ Sin foto: {sin_foto}")
        lineas.append("")

        # ---- Clientes con deuda ----
        clientes_deuda = db.session.query(
            db.func.count(Cliente.id),
            db.func.coalesce(db.func.sum(Cliente.saldo_actual), 0)
        ).filter(Cliente.saldo_actual > 0.01).first()

        lineas.append(f"👥 *Clientes con Deuda*")
        lineas.append(f"   Personas: {clientes_deuda[0]}")
        lineas.append(f"   Total adeudado: ${float(clientes_deuda[1]):,.0f}")
        lineas.append("")
        
        lineas.append("✅ _Fin del reporte. Sistema operativo._")

        return "\n".join(lineas)


def main():
    app = create_app()
    reporte = generar_reporte(app)
    print(reporte)
    print("")
    if enviar_telegram(app, reporte):
        print("✅ Reporte enviado a Telegram exitosamente.")
    else:
        print("❌ No se pudo enviar el reporte a Telegram.")


if __name__ == '__main__':
    main()