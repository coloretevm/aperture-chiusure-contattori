@echo off
pyinstaller --noconfirm --onefile --windowed --name TecnidroAnalisiContatore --icon tecnidro_app_icon.ico --add-data "tecnidro_app_icon.ico;." --exclude-module pytest app.py
