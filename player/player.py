import requests, os, zipfile, subprocess
import sys

SERVER_URL = "http://140.113.17.11:6000"
DOWNLOAD_ROOT = "downloads"  # 所有玩家下載存放根目錄


# ------------------------------
# 基本帳號處理
# ------------------------------

def register(username, password):
    r = requests.post(f"{SERVER_URL}/register", json={
        "username": username,
        "password": password
    })
    res = r.json()
    print(res["message"])
    return res["success"]


def login(username, password):
    r = requests.post(f"{SERVER_URL}/login", json={
        "username": username,
        "password": password
    })
    res = r.json()
    print(res["message"])
    return res["success"]

def logout(username):
    r = requests.post(f"{SERVER_URL}/logout",json={"username": username, "type": "player"})
    res = r.json()
    if res.get("success", False):
        return True
    else:
        return False
    

def get_game_name():
    games = list_store_games()
    if not games:
        return None

    while True:
        choice = input("輸入遊戲編號查看詳細資訊，或輸入 0 返回: ")
        if choice == "0":
            return None

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(games):
            print("請輸入有效的編號")
            continue

        idx = int(choice) - 1
        game_name = games[idx]["game_name"]
        return game_name

def record_play_server(username, game_name, version):
    r = requests.post(f"{SERVER_URL}/player/record_play", json={
        "username": username,
        "game_name": game_name,
        "version": version,
    })
    res = r.json()
    if res.get("success"):
        print(f"已紀錄 {game_name} {version} 的遊玩紀錄")
    else:
        print("紀錄失敗:", res.get("message"))

def list_own_games(username):
    user_dir = os.path.join(DOWNLOAD_ROOT, username)
    if not os.path.exists(user_dir):
        print("你尚未下載任何遊戲")
        return None

    games = [d for d in os.listdir(user_dir) if os.path.isdir(os.path.join(user_dir, d))]
    if not games:
        print("你尚未下載任何遊戲")
        return None

    # 列出遊戲讓玩家選擇
    print("\n=== 你的遊戲列表 ===")
    for idx, g in enumerate(games):
        print(f"{idx+1}. {g}")
    print("====================")

    return games

def choose_game_to_play(games):
    # 玩家輸入 index
    try:
        choice = int(input("請輸入遊戲編號以建立房間，輸入0退出: ")) - 1
        if choice == -1:
            return None
        if choice < 0 or choice >= len(games):
            print("無效編號")
            return None
    except ValueError:
        print("請輸入數字")
        return None

    game_name = games[choice]

    return game_name

def leave_room(username):
    r = requests.post(f"{SERVER_URL}/player/leave_room", json={
        "username": username,
    })
    res = r.json()
    if res.get("success"):
        print(f"已退出房間")
    else:
        print("退出房間失敗:", res.get("message"))



# ------------------------------
# 商城與遊戲資訊（支援索引選擇）
# ------------------------------

def list_store_games():
    r = requests.get(f"{SERVER_URL}/store/games")
    if r.status_code != 200:
        print("無法取得遊戲列表")
        return []

    games = r.json().get("games", [])
    if not games:
        print("目前沒有可下載的遊戲")
        return []

    print("\n=== 商城遊戲列表 ===")
    for idx, g in enumerate(games, 1):
        print(f"{idx}. {g['game_name']} (作者: {g['developer']}, 最新版本: {g['latest_version']})")
    print("====================\n")
    return games

def get_game_details(game_name):
    r = requests.get(f"{SERVER_URL}/store/game/{game_name}")
    if r.status_code != 200:
        print("找不到這款遊戲")
        return None

    meta = r.json()
    print("\n=== 遊戲資訊 ===")
    print(f"名稱: {meta['game_name']}")
    print(f"作者: {meta['developer']}")
    print(f"版本: {meta['latest_version']}")
    print(f"描述: {meta.get('description', '無描述')}")
    print(f"類型: {meta.get('type', '未知')}, 支援玩家數: {meta.get('max_players', '未知')}")
    print("=== 評分與評論 ===")
    for rv in meta.get("reviews", []):
        print(f"{rv['user']} ｜ {rv['rating']}分 ｜ {rv['comment']}")
    print("====================\n")
    return meta

def choose_and_view_game():
    game_name = get_game_name()
    if game_name is None:
        return None
    meta = get_game_details(game_name)
    return meta

# ------------------------------
# 下載遊戲
# ------------------------------

def download_game(username, game_name, latest_version):

    # 設置玩家的下載路徑
    versioned_dir = os.path.join(DOWNLOAD_ROOT, username, game_name, latest_version)
    os.makedirs(versioned_dir, exist_ok=True)

    zip_path = os.path.join(versioned_dir, f"{game_name}.zip")

    print("開始下載遊戲...")

    r = requests.post(
        f"{SERVER_URL}/player/download/{game_name}",
        json={"username": username},
        stream=True
    )

    if r.status_code != 200:
        print("下載失敗:", r.text)
        return False

    # 寫入 zip
    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(1024):
            f.write(chunk)

    # 解壓
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(versioned_dir)

    print(f"下載完成：{versioned_dir}")
    return True



# ------------------------------
# 建立或加入房間並執行遊戲
# ------------------------------
def create_room_and_play(username, game_name):
    
    # 1) 建立房間
    r = requests.post(f"{SERVER_URL}/lobby/create_room", json={
        "username": username,
        "game_name": game_name
    })

    if r.status_code != 200:
        print("建立房間失敗：", r.text)
        return False

    room_id = r.json()["room_id"]
    print(f"房間建立成功！room_id = {room_id}")

    # 2) 要求 lobby 啟動 game server
    r2 = requests.post(f"{SERVER_URL}/lobby/start_room", json={
        "room_id": room_id
    })

    if r2.status_code != 200:
        print("啟動遊戲伺服器失敗：", r2.text)
        return False

    room_info = r2.json()
    host_addr = room_info["host_addr"]
    host_port = room_info["host_port"]
    version = room_info["version"]

    print(f"遊戲伺服器已啟動：{host_addr}:{host_port}")

    GAME_CLIENT_PATH = os.path.join(os.getcwd(), DOWNLOAD_ROOT, username, game_name, version, "game_client.py")
    game_dir = os.path.join(os.getcwd(), DOWNLOAD_ROOT, username, game_name, version)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=game_dir,
        check=True
    )

    # 3) 玩家啟動 game_client.py
    cmd = [
        "python", GAME_CLIENT_PATH,
        "--host", host_addr,
        "--port", str(host_port),
        "--username", username
    ]
    print("啟動遊戲客戶端：", " ".join(cmd))
    subprocess.call(cmd)

    record_play_server(username, game_name, version)
    leave_room(username)
    return True

def list_rooms():
    """取得目前所有房間並列出"""
    r = requests.get(f"{SERVER_URL}/lobby/list_rooms")
    if r.status_code != 200:
        print("無法取得房間列表")
        return [], []

    rooms = r.json().get("rooms", [])
    if not rooms:
        print("目前沒有任何房間")
        return [], []
    # print(rooms)
    room_ids=[]
    print("\n=== 房間列表 ===")
    for idx, room_id in enumerate(rooms):
        print(f"[{idx+1}] {rooms[room_id]['game_name']} (版本 {rooms[room_id]['version']}), "
              f"人數 {len(rooms[room_id]['players'])}/{rooms[room_id]['max_players']}, 狀態: {rooms[room_id]['status']}")
        room_ids.append(room_id)
    print("================\n")
    return rooms, room_ids

def join_room_and_play(username):
    room = None
    rooms, room_ids = list_rooms()
    if not rooms:
        return

    try:
        choice = int(input("輸入要加入房間的 index: ")) -1
        room = rooms[room_ids[choice]]
    except (ValueError, IndexError):
        print("選擇錯誤")
        return

    room_id = room["room_id"]
    game_name = room["game_name"]
    version = room["version"]

    # 檢查玩家是否有下載對應版本
    player_dir = os.path.join("downloads", username, game_name, version)
    if not os.path.exists(player_dir):
        # 玩家沒下載，告知前端選擇是否下載
        while(True):
            print(f"你尚未下載 {game_name} 版本: {version}，輸入1進行下載，輸入0退出")
            choice = int(input())
            if choice == 1:
                download_game(username, game_name, version)
                break
            elif choice == 0:
                return  False
            else:
                continue

    r = requests.post(f"{SERVER_URL}/lobby/join_room", json={
        "username": username,
        "room_id": room_id
    })
    if r.json().get("success", False) == False:
        print(r.json().get("message", "加入房間失敗"))
        return False
    room = r.json().get("room", None)
    print(room)
    if room == None:
        print("加入房間失敗")
        return False
    host_addr = room["host_addr"]
    host_port = room["host_port"]

    if host_addr is None:
        print("房主尚未啟動遊戲伺服器，請稍後再試")
        return False

    print(f"連線到房主：{host_addr}:{host_port}")

    GAME_CLIENT_PATH = os.path.join(os.getcwd(), DOWNLOAD_ROOT, username, game_name, version, "game_client.py")

    game_dir = os.path.join(os.getcwd(), DOWNLOAD_ROOT, username, game_name, version)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=game_dir,
        check=True
    )

    cmd = [
        "python", GAME_CLIENT_PATH,
        "--host", host_addr,
        "--port", str(host_port),
        "--username", username
    ]
    subprocess.call(cmd)
    record_play_server(username, game_name, version)
    leave_room(username)
    return True

def run_game(username):

    # 玩家確認是否建立房間 or 加入房間
    print("\n=== 遊戲啟動選單 ===")
    print("1. 建立房間（你當房主）")
    print("2. 加入房間（輸入 room_id）")
    op = input("> ")

    if op == "1":
        games = list_own_games(username)
        if games is None:
            return False
        
        game_name = choose_game_to_play(games)
        if game_name == None:
            return False

        # 1) 從 server 取得最新版本資訊
        r = requests.get(f"{SERVER_URL}/store/game/{game_name}")
        if r.status_code != 200:
            print("找不到這款遊戲")
            return False
        
        meta = r.json()
        latest_version = meta["latest_version"]

        # 2) 確認玩家本地是否有這個版本
        game_path = os.path.join(DOWNLOAD_ROOT, username, game_name, latest_version)
        if not os.path.exists(game_path):
            print(f"尚未安裝 {game_name} v{latest_version}")
            print("請先下載遊戲再遊玩。")
            return False
        
        return create_room_and_play(username, game_name)

    elif op == "2":
        return join_room_and_play(username)

    else:
        print("無效選項")
        return False



# ------------------------------
# 玩家評分與留言
# ------------------------------

def review_game(username):
    game_name = get_game_name()
    if game_name is None:
        return None

    # 2. 取得遊戲資料
    r = requests.get(f"{SERVER_URL}/store/game/{game_name}")
    if r.status_code != 200:
        print("找不到這款遊戲")
        return None
    meta = r.json()

    # 3. 輸入評分與留言
    while True:
        try:
            rating = int(input("請輸入評分 (1~5): "))
            if 1 <= rating <= 5:
                break
            else:
                print("評分需在 1~5 範圍")
        except ValueError:
            print("請輸入整數數字")

    comment = input("留言（可空白）: ")

    # 4. 送到伺服器
    r = requests.post(f"{SERVER_URL}/store/review/{game_name}", json={
        "username": username,
        "rating": rating,
        "comment": comment
    })

    if r.status_code == 200:
        print("評論成功！")
    else:
        print("評論失敗：", r.text)


# ------------------------------
# 主流程
# ------------------------------

if __name__ == "__main__":
    username = ""
    try:
        # 先登入/註冊
        while True:
            choice = input("選擇操作: [1] 登入 [2] 註冊 : ")

            username = input("Username: ")
            password = input("Password: ")

            if choice == "1" and login(username, password):
                break
            if choice == "2" and register(username, password):
                print("註冊成功，請登入")
            else:
                print("操作失敗，請重試")

        # 玩家主選單
        while True:
            print("\n=== 玩家選單 ===")
            print("1. 查看所有遊戲")
            print("2. 查看遊戲資訊")
            print("3. 下載遊戲")
            print("4. 啟動遊戲")
            print("5. 評價遊戲")
            print("0. 離開")
            op = input("> ")

            if op == "1":
                list_store_games()

            elif op in ["2", "3", "4", "5"]:

                if op == "2":
                    choose_and_view_game()

                elif op == "3":
                    # 詢問遊戲資訊（包含版本）
                    game_name = get_game_name()
                    if game_name is None:
                        continue
                    r = requests.get(f"{SERVER_URL}/store/game/{game_name}")
                    if r.status_code != 200:
                        print("找不到這款遊戲")
                        continue
                    meta = r.json()
                    if not meta:
                        continue
                    latest_version = meta["latest_version"]
                    download_game(username, game_name, latest_version)

                elif op == "4":
                    run_game(username)

                elif op == "5":
                    review_game(username)

            elif op == "0":
                if logout(username):
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