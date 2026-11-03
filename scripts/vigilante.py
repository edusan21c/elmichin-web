# scripts/vigilante.py
"""Vigilante del Sistema: Envia un reporte completo a Telegram."""
import sys
import os
import subprocess
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

# Intentar importar el modelo de auditoría (por si acaso varía el nombre en el futuro)
try:
    from app.models.audit_log import AuditLog
    TIENE_AUDITORIA = True
except ImportError:
    TIENE_AUDITORIA = False

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
        ahora_utc = datetime.utcnow()
        ahora_local = ahora_utc - timedelta(hours=5)
        inicio_hoy_local = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
        inicio_hoy_utc = inicio_hoy_local + timedelta(hours=5)
        
        tiendas = Tienda.query.filter_by(activa=True).all()
        lineas = []
        lineas.append("🤖 *REPORTE DEL SISTEMA EL MICHIN*")
        lineas.append(f"📅 {ahora_local.strftime('%d/%m/%Y %H:%M')}")
        lineas.append("")

        # ---- Estado de Sincronización (Pendientes Globales) ----
        pendientes = ProductoTienda.query.filter_by(sync_estado='pendiente').count()
        if pendientes > 0:
            lineas.append(f"🔄 *Sincronización:* ⚠️ Hay {pendientes} actualizaciones pendientes por enviar.")
        else:
            lineas.append("🔄 *Sincronización:* ✅ Todo sincronizado con las tiendas.")
        lineas.append("")

        # ---- Reporte por tienda ----
        for tienda in tiendas:
            # 1. Productos Activos (Join para ignorar INACTIVOS)
            total_prod = db.session.query(ProductoTienda).join(
                Producto, ProductoTienda.producto_id == Producto.id
            ).filter(
                ProductoTienda.tienda_id == tienda.id,
                db.func.coalesce(Producto.categoria, '') != 'INACTIVO'
            ).count()

            # 2. Stock Bajo
            stock_bajo = db.session.query(ProductoTienda).join(
                Producto, ProductoTienda.producto_id == Producto.id
            ).filter(
                ProductoTienda.tienda_id == tienda.id,
                db.func.coalesce(Producto.categoria, '') != 'INACTIVO',
                ProductoTienda.cantidad > 0,
                ProductoTienda.cantidad <= 5
            ).count()

            # 3. Agotados
            agotados = db.session.query(ProductoTienda).join(
                Producto, ProductoTienda.producto_id == Producto.id
            ).filter(
                ProductoTienda.tienda_id == tienda.id,
                db.func.coalesce(Producto.categoria, '') != 'INACTIVO',
                ProductoTienda.cantidad <= 0
            ).count()

            # 4. Ventas de hoy
            ventas_hoy = db.session.query(
                db.func.count(Factura.id),
                db.func.coalesce(db.func.sum(Factura.total), 0)
            ).filter(Factura.tienda_id == tienda.id, Factura.fecha_hora >= inicio_hoy_utc).first()

            num_facturas = ventas_hoy[0] or 0
            monto_hoy = float(ventas_hoy[1] or 0)

            # 5. Estado de Conexión (Basado en última actividad de la tienda)
            max_factura = db.session.query(db.func.max(Factura.sync_fecha)).filter(Factura.tienda_id == tienda.id).scalar()
            max_cliente = db.session.query(db.func.max(Cliente.sync_fecha)).filter(Cliente.tienda_id == tienda.id).scalar()
            
            fechas = [f for f in [max_factura, max_cliente] if f is not None]
            ultima_conexion = max(fechas) if fechas else None
            
            estado_conexion = "⚪ Sin actividad"
            if ultima_conexion:
                diff = ahora_utc - ultima_conexion
                if diff > timedelta(hours=4):
                    estado_conexion = f"🔴 Posible Apagada (Hace {diff.seconds//3600}h)"
                elif diff > timedelta(minutes=45):
                    estado_conexion = f"🟡 Sin reportar (Hace {diff.seconds//60}m)"
                else:
                    estado_conexion = "🟢 Activa y Reportando"

            lineas.append(f"🏪 *{tienda.nombre}* - {estado_conexion}")
            lineas.append(f"   📦 Productos activos: {total_prod}")
            lineas.append(f"   ⚠️ Stock bajo: {stock_bajo}  |  ❌ Agotados: {agotados}")
            lineas.append(f"   💰 Ventas hoy: ${monto_hoy:,.0f} ({num_facturas} fact.)")
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

        # ---- Chismes del Sistema (Auditoría) ----
        if TIENE_AUDITORIA:
            try:
                logs = AuditLog.query.order_by(AuditLog.fecha.desc()).limit(5).all()
                if logs:
                    lineas.append(f"🕵️ *Últimos Movimientos (Chismes):*")
                    for l in logs:
                        fecha_str = l.fecha.strftime('%H:%M') if l.fecha else '---'
                        usuario = getattr(l, 'usuario_nombre', 'Sistema')
                        accion = l.accion.replace('_', ' ').capitalize() if l.accion else 'Acción'
                        detalle = (l.detalle[:40] + '...') if l.detalle and len(l.detalle) > 40 else l.detalle
                        
                        lineas.append(f"   • {fecha_str} | {usuario} hizo: _{accion}_")
                        if detalle:
                            lineas.append(f"     ↳ {detalle}")
                    lineas.append("")
            except Exception as e:
                lineas.append(f"🕵️ _No se pudieron cargar los chismes: {e}_")
                lineas.append("")

        # ---- Estado del Código (Git) ----
        try:
            git_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=r'C:\michin_web', text=True).strip()
            git_msg = subprocess.check_output(['git', 'log', '-1', '--pretty=%s'], cwd=r'C:\michin_web', text=True).strip()
            lineas.append(f"💻 *Versión:* `{git_hash}`")
            lineas.append(f"   _Último cambio:_ {git_msg}")
        except Exception as e:
            lineas.append("💻 *Versión:* No se pudo leer Git.")

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