@echo off
cd /d "%~dp0"
REM Active l'environnement virtuel si besoin :
REM call venv\Scripts\activate

set FLASK_APP=app.py
set FLASK_ENV=development
flask run

pause