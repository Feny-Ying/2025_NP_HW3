# 2025 NP HW3 – Player Demo (Virtualenv)

本作業使用 Python 撰寫，已提供 **虛擬環境與啟動腳本**，助教無需手動安裝套件即可執行。

---

## 專案結構
player/
├── player.py
├── downloads/ # 遊戲 client 下載後生成
├── requirements.txt # requests + pygame
├── run.bat # Windows 啟動腳本
└── run.sh # Linux / macOS 啟動腳本


## Demo 執行流程

### Step 1. 下載專案

```bash
git clone https://github.com/Feny-Ying/2025_NP_HW3.git
cd 2025_NP_HW3/player
```

---

---

## 系統需求

- Python 3.10 或以上  
- Windows / Linux / macOS

---

## Demo 執行方式

### Windows

1. 打開 Terminal，進入 `player` 資料夾：
```powershell
cd /path/to/HW3/player
```
2. 確保 run.sh 有執行權限：
```powershell
chmod +x run.sh
```
3. 執行啟動腳本：
```powershell
run.sh
```

### Linux

1. 打開 PowerShell，進入 `player` 資料夾：
```bash
cd D:\NP\HW3\player
```
2. 確保啟動腳本有執行權限：
```bash
chmod +x run.sh
```
3. 執行啟動腳本：
```bash
run.bat
```
---

## 說明

* `player.py` 為入口程式
* `game_client.py` 由 `player.py` 於執行期間動態下載並啟動
* 各遊戲的 Python 套件需求皆包含在其對應的 `requirements.txt` 中
---

