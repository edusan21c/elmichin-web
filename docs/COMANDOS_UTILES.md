# Comandos útiles - El Michín

## Datos importantes
- PostgreSQL password: Michin2026!Seguro
- SYNC_KEY: vKtm_E5Pfh1Xgo64B-fhB8fcf3xNhYaJOlGYxVhhLrlFN--sGmDqyg
- Central: https://central.elmichin.com
- Login programador: programador / eduar1985
- Login cajero1: cajero1 / cajero123
- Login cajero2: cajero2 / cajero123

## Servicios
Get-Service MichinFlask, cloudflared
Restart-Service MichinFlask
Get-Content C:\michin_web\logs\flask_stderr.log -Tail 30

## Base de datos
psql -U postgres -d michin_central
psql -U postgres -d michin_t1

## Sync y backup
python scripts\sync_worker.py
python scripts\test_sync_simulado.py
python scripts\backup_auto.py

## Git
git add . && git commit -m "mensaje"
git push origin main