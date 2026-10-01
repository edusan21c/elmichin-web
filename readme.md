# El Michin - Sistema de Gestion

Sistema web multi-tienda para dulcería/cigarrería.

## Arquitectura

- **Central**: PC del dueño. Base de datos maestra + Panel admin.
- **Tienda Local**: 1 PC por tienda. Sistema local + sync al central.

## Stack

| Componente | Tecnologia |
|---|---|
| Backend | Flask 3.0 + SQLAlchemy 2.0 |
| Base de datos | PostgreSQL 17 |
| Frontend | Jinja2 + Bootstrap 5 |
| Auth | Flask-Login + bcrypt |
| Servidor prod | Waitress |
| Tunel HTTPS | Cloudflare Tunnel |
| Servicios | NSSM |

## Modulos

- Autenticacion (programador / admin / operario)
- Inventario con stock por tienda
- Facturacion completa
- Venta rapida (codigo de barras)
- Reportes de ventas
- Cuentas por cobrar
- Gestion de usuarios

## Instalacion Central

```powershell
git clone <URL> C:\michin_web
cd C:\michin_web
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
# Crear .env con MODO=central
psql -U postgres -c "CREATE DATABASE michin_central;"
flask db upgrade