from flask import Flask, request, jsonify
import os, shutil, zipfile, io, json
from accounts import AccountManager

app = Flask(__name__)
UPLOAD_DIR = "uploaded_games"  # 所有開發者遊戲存放根目錄
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Developer 帳號管理
dev_manager = AccountManager("developer")


# ==========================
# 工具函式
# ==========================
def get_user_game_dir(username, game_name):
    return os.path.join(UPLOAD_DIR, username, game_name)


def load_meta(username, game_name):
    meta_path = os.path.join(get_user_game_dir(username, game_name), "meta.json")
    if not os.path.exists(meta_path):
        return None
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_meta(username, game_name, meta):
    meta_path = os.path.join(get_user_game_dir(username, game_name), "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4, ensure_ascii=False)


# ==========================
# 註冊 / 登入 / 登出
# ==========================
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    success, msg = dev_manager.register(username, password)
    return jsonify({"success": success, "message": msg})


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # 檢查是否已經登入
    if dev_manager.is_logged_in(username):
        return jsonify({"success": False, "message": "此帳號已登入，無法重複登入"}), 403

    success, msg = dev_manager.login(username, password)
    return jsonify({"success": success, "message": msg})


@app.route("/logout", methods=["POST"])
def logout():
    data = request.json
    username = data.get("username")
    success, msg = dev_manager.logout(username)
    return jsonify({"success": success, "message": msg})


# ==========================
# 上架遊戲
# ==========================
@app.route("/upload_game", methods=["POST"])
def upload_game():
    try:
        username = request.form.get("username")
        game_name = request.form.get("game_name")
        version = request.form.get("version")
        description = request.form.get("description", "")
        game_type = request.form.get("type", "CLI")
        max_players = int(request.form.get("max_players", 1))
        config_data = request.form.get("config", "{}")

        if not dev_manager.is_logged_in(username):
            return "請先登入", 403
        if not version:
            return "上傳必須提供版本號", 400

        # 遊戲資料夾以遊戲名稱為主
        game_dir = os.path.join(UPLOAD_DIR, game_name)
        version_dir = os.path.join(game_dir, version)
        os.makedirs(version_dir, exist_ok=True)

        # 解壓 zip 檔到版本資料夾
        import io, zipfile
        file = request.files['file']
        file_bytes = io.BytesIO(file.read())
        file_bytes.seek(0)
        with zipfile.ZipFile(file_bytes, 'r') as zip_ref:
            zip_ref.extractall(version_dir)

        # 建立或更新 meta.json
        import json
        meta_path = os.path.join(game_dir, "meta.json")
        meta = {
            "developer": username,
            "game_name": game_name,
            "description": description,
            "type": game_type,
            "max_players": max_players,
            "config": config_data,
            "latest_version": version,
            "versions": {version: description}
        }
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                old_meta = json.load(f)
            # 合併舊版本歷史
            meta["versions"].update(old_meta.get("versions", {}))

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return f"遊戲 {game_name} 上架成功，版本 {version}"

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"伺服器錯誤: {e}", 500


# ==========================
# 更新遊戲版本 (D2)
# ==========================
@app.route("/update_game", methods=["POST"])
def update_game():
    try:
        username = request.form.get("username")
        game_name = request.form.get("game_name")
        new_version = request.form.get("new_version")
        new_description = request.form.get("description", "")
        game_type = request.form.get("type", "CLI")
        max_players = int(request.form.get("max_players", 1))
        config_data = request.form.get("config", "{}")

        if not dev_manager.is_logged_in(username):
            return "請先登入", 403

        game_dir = os.path.join(UPLOAD_DIR, game_name)
        if not os.path.exists(game_dir):
            return "無此遊戲可更新", 404

        # 驗證開發者身份
        meta_path = os.path.join(game_dir, "meta.json")
        if not os.path.exists(meta_path):
            return "meta.json 不存在，無法驗證開發者", 500
        import json
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("developer") != username:
            return "無權限更新此遊戲", 403

        # 驗證版本號
        if not new_version or new_version.strip() == "":
            return "版本號不可為空", 400
        version_path = os.path.join(game_dir, new_version)
        if os.path.exists(version_path):
            return "版本號已存在", 400

        # 建立新版本資料夾
        os.makedirs(version_path, exist_ok=True)

        # 解壓新版本
        import io, zipfile
        file = request.files['file']
        file_bytes = io.BytesIO(file.read())
        file_bytes.seek(0)
        with zipfile.ZipFile(file_bytes, 'r') as zip_ref:
            zip_ref.extractall(version_path)

        # 更新 meta.json
        meta["latest_version"] = new_version
        meta["description"] = new_description or meta.get("description", "")
        meta["type"] = game_type
        meta["max_players"] = max_players
        meta["config"] = config_data
        meta.setdefault("versions", {})[new_version] = new_description

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return f"遊戲 {game_name} 已更新到版本 {new_version}"

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"伺服器錯誤: {e}", 500


# ==========================
# 下架遊戲
# ==========================
@app.route("/remove_game", methods=["POST"])
def remove_game():
    data = request.json
    username = data.get("username")
    game_name = data.get("game_name")

    if not dev_manager.is_logged_in(username):
        return jsonify({"success": False, "message": "請先登入"}), 403
    
    game_dir = os.path.join(UPLOAD_DIR, game_name)

    if not os.path.exists(game_dir):
        return jsonify({"success": False, "message": "遊戲不存在"}), 404
    
    # 驗證開發者身份
    meta_path = os.path.join(game_dir, "meta.json")
    if not os.path.exists(meta_path):
        return "meta.json 不存在，無法驗證開發者", 500
    import json
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("developer") != username:
        return "無權限更新此遊戲", 403

    shutil.rmtree(game_dir)
    return jsonify({"success": True, "message": f"遊戲 {game_name} 已下架"})


# ==========================
# 列出開發者的遊戲
# ==========================
@app.route("/list_my_games", methods=["GET"])
def list_my_games():
    username = request.args.get("username")
    if not dev_manager.is_logged_in(username):
        return jsonify({"games": []})

    games = []
    for game_name in os.listdir(UPLOAD_DIR):
        game_dir = os.path.join(UPLOAD_DIR, game_name)
        meta_path = os.path.join(game_dir, "meta.json")
        if os.path.isdir(game_dir) and os.path.exists(meta_path):
            import json
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("developer") == username:
                games.append({
                    "game_name": game_name,
                    "latest_version": meta.get("latest_version"),
                    "description": meta.get("description", "")
                })

    return jsonify({"games": games})


if __name__ == "__main__":
    app.run(port=5000)
