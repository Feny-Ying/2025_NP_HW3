from flask import Flask, send_file, jsonify, request
import os
import shutil
from accounts import AccountManager  # 永久化帳號 + session
import json
from uuid import uuid4
from room_manager import RoomManager
import subprocess

app = Flask(__name__)
UPLOAD_DIR = "uploaded_games"
ROOMS_FILE = "rooms.json"

# Player 帳號管理（永久保存帳號和登入 session）
player_manager = AccountManager("player")
room_manager = RoomManager()

# --------------------------
# 帳號路由
# --------------------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    success, msg = player_manager.register(username, password)
    return jsonify({"success": success, "message": msg})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # 檢查是否已經登入
    if player_manager.is_logged_in(username):
        return jsonify({"success": False, "message": "此帳號已登入，無法重複登入"}), 403

    success, msg = player_manager.login(username, password)
    return jsonify({"success": success, "message": msg})

@app.route("/logout", methods=["POST"])
def logout():
    data = request.json
    username = data.get("username")
    success, msg = player_manager.logout(username)
    return jsonify({"success": success, "message": msg})


# ============================================================
# Helper：讀取遊戲 metadata.json
# ============================================================
def load_metadata(game_name):
    meta_path = os.path.join(UPLOAD_DIR, game_name, "meta.json")
    if not os.path.exists(meta_path):
        return None

    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)
    

# ============================================================
# 商城：列出所有遊戲
# ============================================================
@app.route("/store/games", methods=["GET"])
def store_games():
    if not os.path.exists(UPLOAD_DIR):
        return jsonify({"games": []})

    result = []
    for game_name in os.listdir(UPLOAD_DIR):
        game_dir = os.path.join(UPLOAD_DIR, game_name)
        if not os.path.isdir(game_dir):
            continue

        meta = load_metadata(game_name)
        if not meta:
            continue

        result.append({
            "game_name": game_name,
            "developer": meta.get("developer", "unknown"),
            "latest_version": meta.get("latest_version")
        })

    return jsonify({"games": result})

# ============================================================
# 商城：取得遊戲詳細資訊
# ============================================================
@app.route("/store/game/<game_name>", methods=["GET"])
def store_game_detail(game_name):
    meta = load_metadata(game_name)
    if not meta:
        return jsonify({"error": "game not found or metadata missing"}), 404

    # 加入 review
    review_file = os.path.join(UPLOAD_DIR, game_name, "reviews.json")
    reviews = []
    if os.path.exists(review_file):
        reviews = json.load(open(review_file, "r", encoding="utf-8"))

    meta["reviews"] = reviews
    meta["latest_version"] = meta.get("latest_version")

    return jsonify(meta)

# ============================================================
# 玩家下載遊戲（自動給最新版本）
# ============================================================
@app.route("/player/download/<game_name>", methods=["POST"])
def player_download(game_name):
    username = request.json.get("username")

    if not player_manager.is_logged_in(username):
        return jsonify({"success": False, "message": "請先登入"}), 403

    meta = load_metadata(game_name)
    if not meta:
        return jsonify({"success": False, "message": "遊戲不存在"}), 404

    latest = meta.get("latest_version")
    version_dir = os.path.join(UPLOAD_DIR, game_name, latest)

    # zip 位置
    zip_path = os.path.join(UPLOAD_DIR, f"{game_name}_{latest}.zip")

    # 打包 zip（如果不存在）
    if not os.path.exists(zip_path):
        shutil.make_archive(
            base_name=os.path.join(UPLOAD_DIR, f"{game_name}_{latest}"),
            format="zip",
            root_dir=version_dir
        )

    return send_file(zip_path, as_attachment=True)

# ============================================================
# 紀錄玩家遊玩過的遊戲
# ============================================================
@app.route("/player/record_play", methods=["POST"])
def record_play():
    data = request.json
    username = data.get("username")
    game_name = data.get("game_name")
    version = data.get("version")

    if not player_manager.is_logged_in(username):
        return jsonify({"success": False, "message": "請先登入"}), 403

    # 1. 記錄遊戲紀錄
    success = player_manager.record_play(username, game_name, version)
    if not success:
        return jsonify({"success": False, "message": "紀錄失敗"}), 400


    return jsonify({"success": True, "message": "紀錄成功"})

# ============================================================
# 玩家留言 / 評分
# ============================================================
@app.route("/store/review/<game_name>", methods=["POST"])
def store_review(game_name):
    data = request.json
    username = data.get("username")
    rating = data.get("rating")
    comment = data.get("comment", "")

    if not player_manager.is_logged_in(username):
        return jsonify({"success": False, "message": "請先登入"}), 403
    if not player_manager.has_played(username, game_name):
        return jsonify({"success": False, "message": "你尚未玩過此遊戲，無法評論！"}), 403

    review_file = os.path.join(UPLOAD_DIR, game_name, "reviews.json")
    reviews = []
    if os.path.exists(review_file):
        reviews = json.load(open(review_file, "r", encoding="utf-8"))

    reviews.append({
        "user": username,
        "rating": rating,
        "comment": comment
    })

    json.dump(reviews, open(review_file, "w", encoding="utf-8"), ensure_ascii=False)
    return jsonify({"success": True, "message": "評論成功"})


# ============================================================
# 大廳：建立房間
# ============================================================
def load_rooms():
    with open(ROOMS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_rooms(r):
    with open(ROOMS_FILE, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)

def generate_room_id():
    return str(uuid4())[:8]

@app.route("/lobby/create_room", methods=["POST"])
def create_room():
    print("[DEBUG] 建立房間中")
    data = request.json
    game_name = data["game_name"]
    username = data["username"]

    # 取得 latest version
    meta = load_metadata(game_name)
    latest_version = meta.get("latest_version", None)
    if latest_version is None:
        return {"error": "找不到遊戲版本"}, 400
    
    maxplayers = meta.get("max_players", 2)
    print("[DEBUG] 取得房間資料中")
    # 生成房間 ID
    room_id = generate_room_id()

    ok, msg = room_manager.create_room(
        room_id=room_id,
        game_name=game_name,
        version=latest_version,
        host=username,
        maxplayers = maxplayers
    )
    print("[DEBUG] 建立完成")
    if not ok:
        return {"error": msg}, 400

    return {"room_id": room_id}

@app.route("/lobby/start_room", methods=["POST"])
def start_room():
    data = request.json
    room_id = data["room_id"]

    room = room_manager.get_room(room_id)
    if not room:
        return jsonify({"error": "room not found"}), 404
    max_players = room["max_players"]
    game_name = room["game_name"]
    version = room["version"]
    game_server_path = room["game_server_path"]
    GAME_SERVER_PATH = os.path.join(os.getcwd(), game_server_path)

    # pick random free port
    import socket
    s = socket.socket()
    s.bind(('0.0.0.0', 0))
    port = s.getsockname()[1]
    s.close()

    # start game server subprocess
    cmd = [
        "python", GAME_SERVER_PATH,
        "--host", "127.0.0.1",
        "--port", str(port),
        "--max_players", str(max_players)
    ]

    print("[Lobby] Starting game server:", " ".join(cmd))
    proc = subprocess.Popen(cmd)

    # save host info
    room["host_addr"] = "127.0.0.1"
    room["host_port"] = port
    room["status"] = "running"
    room_manager._save()

    return jsonify({
        "status": "ok",
        "room_id": room_id,
        "host_addr": "127.0.0.1",
        "host_port": port,
        "version" : version
    })

@app.route("/lobby/list_rooms", methods=["GET"])
def list_rooms():
    rooms = room_manager.get_rooms()
    if rooms is None:
        return jsonify({"success": False, "message": "rooms not found"}), 404
    return jsonify({"success": True, "rooms": rooms})

@app.route("/lobby/join_room", methods=["POST"])
def join_room():
    data = request.json
    username = data["username"]
    room_id = data["room_id"]

    # 取得房間資訊
    room = room_manager.get_room(room_id)
    if not room:
        return jsonify({"success": False, "message": "room not found"}), 404

    # 檢查房間人數上限
    if len(room["players"]) >= room["max_players"]:
        return jsonify({"success": False, "message": "房間已滿"}), 403

    # 將玩家加入房間
    room["players"].append(username)
    room_manager._save()

    return jsonify({
        "success": True,
        "message": f"已加入房間 {room_id}",
        "room": room
    })

@app.route("/player/leave_room", methods=["POST"])
def player_leave_room():
    data = request.json
    username = data.get("username")
    if not username:
        return jsonify({"success": False, "msg": "缺少 username"})

    success, msg = room_manager.leave_room(username)
    return jsonify({"success": success, "msg": msg})


# ============================================================
# 啟動伺服器
# ============================================================
if __name__ == "__main__":
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    app.run(host="0.0.0.0", port=6000, debug=True)
