@echo off
REM 建立虛擬環境
python -m venv venv

REM 啟動虛擬環境
call venv\Scripts\activate

REM 安裝套件
pip install --upgrade pip
pip install requests

REM 執行 player.py
python player.py

REM 完成後關閉虛擬環境
deactivate
pause
