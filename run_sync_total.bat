@echo off
cd C:\michin_web
C:\michin_web\venv\Scripts\pythonw.exe C:\michin_web\scripts\push_worker.py
C:\michin_web\venv\Scripts\pythonw.exe C:\michin_web\scripts\sync_worker.py
