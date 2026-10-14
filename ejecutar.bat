@echo off
REM Abre la interfaz del sistema experto P9 en el navegador.
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python -m streamlit run interfaz.py
pause
