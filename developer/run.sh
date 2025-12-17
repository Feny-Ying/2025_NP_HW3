#!/bin/bash

# 建立虛擬環境
python3 -m venv venv

# 啟動虛擬環境
source venv/bin/activate

# 安裝套件
pip install --upgrade pip
pip install requests

# 執行 player.py
python developer.py

# 完成後關閉虛擬環境
deactivate
