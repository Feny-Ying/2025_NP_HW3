# 2025 NP HW3 – Player Docker Demo

本作業已使用 **Docker** 封裝執行環境，助教無需手動安裝任何 Python 套件，只需依照以下步驟即可完成 demo。

---

## 環境需求

* 已安裝 **Docker Desktop**
* 作業系統：Windows / Linux / macOS 皆可

---

## Demo 執行流程

### Step 1. 下載專案

```bash
git clone https://github.com/Feny-Ying/2025_NP_HW3.git
cd 2025_NP_HW3/player
```

---

### Step 2. 建立 Docker Image

```bash
docker build -t hw3-player .
```

> 第一次執行會稍久，因為需要下載 Python 映像檔。

---

### Step 3. 啟動 Player（自動執行）

```bash
docker run -it hw3-player
```

Container 啟動後會自動執行 `player.py`，並由 `player.py`：

1. 下載並解壓遊戲 client
2. 安裝該遊戲所需的 Python 套件（requirements.txt）
3. 以 subprocess 啟動 `game_client.py`
4. 開始遊戲互動流程

---

## 說明

* `player.py` 為入口程式
* `game_client.py` 由 `player.py` 於執行期間動態下載並啟動
* 各遊戲的 Python 套件需求皆包含在其對應的 `requirements.txt` 中
* Docker container 內使用同一個 Python 環境，確保 subprocess 能正確執行
---

