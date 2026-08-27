@echo off
python -m pip install pyinstaller --upgrade
python -m PyInstaller --onefile --noconsole roblox.py
pause