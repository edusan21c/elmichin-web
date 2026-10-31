import subprocess
import os
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def limpiar_temporales():
    log("Limpiando temporales de Windows...")
    subprocess.run(["powershell", "-Command", "Remove-Item -Path \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue"], capture_output=True)
    subprocess.run(["powershell", "-Command", "Remove-Item -Path \"C:\\Windows\\Temp\\*\" -Recurse -Force -ErrorAction SilentlyContinue"], capture_output=True)

def limpiar_descargas():
    log("Limpiando descargas mayores a 30 días...")
    # Ruta nueva de Descargas en el Disco D
    ruta_descargas = r"D:\01_USUARIO_EDUSA\03_Descargas"
    if not os.path.exists(ruta_descargas): return
    ps_cmd = f"""
    Add-Type -AssemblyName Microsoft.VisualBasic
    $fecha = (Get-Date).AddDays(-30)
    $archivos = Get-ChildItem -Path "{ruta_descargas}" -File -Recurse -ErrorAction SilentlyContinue | Where-Object {{ $_.LastWriteTime -lt $fecha }}
    $archivos | ForEach-Object {{ [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($_.FullName, 'OnlyErrorDialogs', 'SendToRecycleBin') }}
    """
    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)

def limpiar_pantallazos():
    log("Limpiando pantallazos viejos...")
    # Ruta de capturas (ajustada a la carpeta que movimos)
    ruta_capturas = r"D:\01_USUARIO_EDUSA\04_Imagenes\Screenshots"
    if not os.path.exists(ruta_capturas):
        ruta_capturas = r"D:\01_USUARIO_EDUSA\04_Imagenes\Capturas de pantalla"
    
    if not os.path.exists(ruta_capturas): return
    
    ps_cmd = f"""
    Add-Type -AssemblyName Microsoft.VisualBasic
    $fecha = (Get-Date).AddDays(-30)
    $archivos = Get-ChildItem -Path "{ruta_capturas}" -Filter *.png -File -ErrorAction SilentlyContinue | Where-Object {{ $_.LastWriteTime -lt $fecha }}
    $archivos | ForEach-Object {{ [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($_.FullName, 'OnlyErrorDialogs', 'SendToRecycleBin') }}
    """
    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)

def vaciar_papelera():
    log("Vaciando papelera de reciclaje...")
    subprocess.run(["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"], capture_output=True)

if __name__ == "__main__":
    log("=== INICIANDO LIMPIEZA AUTOMÁTICA ===")
    limpiar_temporales()
    limpiar_descargas()
    limpiar_pantallazos()
    vaciar_papelera()
    log("=== LIMPIEZA COMPLETADA ===")