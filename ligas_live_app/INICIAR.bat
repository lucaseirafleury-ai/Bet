@echo off
title Painel de Sinais - Ligas Live
cd /d "%~dp0"

echo Verificando dependencias...
pip install -r requirements.txt --quiet

echo.
echo Iniciando o painel...
echo O navegador vai abrir automaticamente em alguns segundos.
echo Para PARAR o app, feche esta janela ou pressione Ctrl+C.
echo.

python app.py

pause
