import requests, os, io, zipfile, yaml

SERVER_URL = "http://127.0.0.1:5000"
GAMES_DIR = "games"

# -------------------------
# 帳號相關
# -------------------------
def register(username, password):
    r = requests.post(f"{SERVER_URL}/register",
                      json={"username": username, "password": password, "type": "developer"})
    res = r.json()
    print(res.get("message", ""))
    return res.get("success", False)

def login(username, password):
    r = requests.post(f"{SERVER_URL}/login",
                      json={"username": username, "password": password, "type": "developer"})
    res = r.json()
    print(res.get("message", ""))
    return res.get("success", False)

def logout(username):
    r = requests.post(f"{SERVER_URL}/logout",json={"username": username, "type": "developer"})
    res = r.json()
    if res.get("success", False):
        return True
    else:
        return False

# -------------------------
# 工具：將遊戲 ZIP 到記憶體
# -------------------------
def zip_game_to_memory(game_dir):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(game_dir):
            for f in files:
                file_path = os.path.join(root, f)
                arcname = os.path.relpath(file_path, game_dir)
                zipf.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

# -------------------------
# 上架 / 更新 遊戲
# -------------------------
def upload_game(username, game_name):
    game_dir = os.path.join(GAMES_DIR, game_name)
    if not os.path.exists(game_dir) or not os.listdir(game_dir):
        print("❌ 遊戲資料夾不存在或為空！")
        return

    # 1. 基本資訊
    description = input("請輸入遊戲介紹描述: ")
    print("遊戲類型選擇：1.CLI 2.GUI 3.PVP 4.PVE")
    game_type = {"1":"CLI","2":"GUI","3":"PVP","4":"PVE"}.get(input("選擇類型: "), "CLI")
    max_players = input("最大玩家數（預設1）: ") or "1"
    version = input("遊戲版本號 (例如 1.0): ").strip()

    # 2. config 檔案（可選）
    config_data = ""
    if input("是否附加 config.yml？(y/n): ") == "y":
        config_path = os.path.join(game_dir, "config.yml")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = f.read()
            print("✔ 已附加 config.yml")
        else:
            print("⚠ 找不到 config.yml，跳過")

    # ZIP 遊戲資料夾
    zip_buffer = zip_game_to_memory(game_dir)

    files = {'file': (f"{game_name}.zip", zip_buffer)}
    data = {
        "username": username,
        "game_name": game_name,
        "description": description,
        "type": game_type,
        "max_players": max_players,
        "version": version,
        "config": config_data
    }

    r = requests.post(f"{SERVER_URL}/upload_game", files=files, data=data)
    print(r.text)

def update_game(username, game_name):
    game_dir = os.path.join(GAMES_DIR, game_name)
    if not os.path.exists(game_dir) or not os.listdir(game_dir):
        print("更新的遊戲資料夾不存在或為空！")
        return

    # 輸入新版本號
    new_version = input("輸入新版本號 (例如 1.1): ").strip()
    if not new_version:
        print("版本號不可為空")
        return

    # 可選輸入描述、類型、最大人數、config
    description = input("輸入版本描述（可選）: ").strip()
    print("遊戲類型選擇：1.CLI 2.GUI 3.PVP 4.PVE")
    game_type = {"1":"CLI","2":"GUI","3":"PVP","4":"PVE"}.get(input("選擇類型: "), "CLI")
    max_players = input("最大玩家數 (default 1): ").strip() or "1"
    config_data = ""
    if input("是否附加 config.yml？(y/n): ") == "y":
        config_path = os.path.join(game_dir, "config.yml")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = f.read()
            print("✔ 已附加 config.yml")
        else:
            print("⚠ 找不到 config.yml，跳過")

    # 打包遊戲成 zip
    zip_buffer = zip_game_to_memory(game_dir)
    files = {'file': (f"{game_name}.zip", zip_buffer)}
    data = {
        "username": username,
        "game_name": game_name,
        "new_version": new_version,
        "description": description,
        "type": game_type,
        "max_players": max_players,
        "config": config_data
    }

    # 呼叫 server 更新遊戲
    r = requests.post(f"{SERVER_URL}/update_game", files=files, data=data)
    print(r.text)

def remove_game(username, game_name):
    r = requests.post(f"{SERVER_URL}/remove_game",
                      json={"username": username, "game_name": game_name})
    print(r.text)

def list_my_games(username):
    r = requests.get(f"{SERVER_URL}/list_my_games", params={"username": username})
    games = r.json().get("games", [])
    print("\n🟦 我的遊戲列表:")
    for g in games:
        print("-", g)
    return games

# -------------------------
# 主流程
# -------------------------
if __name__ == "__main__":
    username = ""
    password = ""

    try:
        # 登入/註冊循環
        while True:
            choice = input("選擇操作: [1] 登入 [2] 註冊 : ")
            if choice not in ["1", "2"]:
                print("請輸入 1 或 2")
                continue

            username = input("Username: ")
            password = input("Password: ")

            if choice == "1":
                if login(username, password):
                    break
                else:
                    print("登入失敗，可重新選擇")
            else:
                if register(username, password):
                    print("註冊成功，請使用登入")
                else:
                    print("註冊失敗，帳號可能已被使用")

        # 開發者選單
        while True:
            print("\n== 開發者主選單 ==")
            print("1. 上架新遊戲")
            print("2. 更新遊戲版本")
            print("3. 下架遊戲")
            print("4. 查看我的遊戲")
            print("0. 登出 / 離開")

            op = input("選擇操作: ")

            if op == "1":
                upload_game(username, input("遊戲名稱: "))

            elif op == "2":
                my_games = list_my_games(username)

                if not my_games:
                    print("你目前沒有任何遊戲")
                else:
                    print("你的遊戲列表：")
                    for i, g in enumerate(my_games):
                        print(f"{i}: {g['game_name']}")

                    try:
                        idx = int(input("請輸入要更新的遊戲編號: "))
                        if 0 <= idx < len(my_games):
                            game_name = my_games[idx]["game_name"]
                            update_game(username, game_name)
                        else:
                            print("編號不存在")
                    except ValueError:
                        print("請輸入有效的數字")

            elif op == "3":
                my_games = list_my_games(username)

                if not my_games:
                    print("你目前沒有任何遊戲")
                else:
                    print("你的遊戲列表：")
                    for i, g in enumerate(my_games):
                        print(f"{i}: {g['game_name']}")

                    try:
                        idx = int(input("請輸入要下架的遊戲編號: "))
                        if 0 <= idx < len(my_games):
                            game_name = my_games[idx]["game_name"]
                            remove_game(username, game_name)
                        else:
                            print("編號不存在")
                    except ValueError:
                        print("請輸入有效的數字")

            elif op == "4":
                list_my_games(username)

            elif op == "0":
                if (logout(username)):
                    print("登出，離開系統")
                    break
                else:
                    print("登出失敗")
                    
            else:
                print("無效選項")

    except Exception as e:
        print("程式發生未捕捉錯誤:", e)
        import traceback
        traceback.print_exc()
    finally:
        # 確保斷線或異常時自動登出
        if username:
            try:
                logout(username)
                print(f"{username} 已自動登出")
            except Exception as e:
                print("自動登出失敗:", e)
