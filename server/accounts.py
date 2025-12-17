import json
import os
from threading import RLock

LOCK = RLock()

class AccountManager:
    def __init__(self, account_type):
        self.account_type = account_type
        self.filename = f"{account_type}_accounts.json"
        self.session_file = f"{account_type}_sessions.json"
        
        # 初始化帳號檔案
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump({}, f)

        # 初始化 session 檔案
        if not os.path.exists(self.session_file):
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)

        self._load_sessions()

    # ------------------------------
    # 帳號操作
    # ------------------------------
    def _load_accounts(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_accounts(self, accounts):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)

    def _load_sessions(self):
        if os.path.exists(self.session_file):
            with open(self.session_file, 'r', encoding='utf-8') as f:
                self.sessions = json.load(f)
        else:
            self.sessions = {}

    def _save_sessions(self):
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(self.sessions, f, indent=2, ensure_ascii=False)

    # ------------------------------
    # 註冊 / 登入 / 登出
    # ------------------------------
    def register(self, username, password):
        with LOCK:
            accounts = self._load_accounts()
            if username in accounts:
                return False, "帳號已被使用"
            if self.account_type == "developer":
                accounts[username] = {
                "password": password,
                }
            elif self.account_type == "player":
                accounts[username] = {
                    "password": password,
                    "records": {}  # 紀錄遊玩過的遊戲版本
                }
            else:
                return False, "未知的帳號類型"
            self._save_accounts(accounts)
            self.sessions[username] = False
            self._save_sessions()
            return True, "註冊成功"

    def login(self, username, password):
        with LOCK:
            accounts = self._load_accounts()
            user = accounts.get(username)
            if not user or user.get("password") != password:
                return False, "帳號或密碼錯誤"

            # 新登入覆蓋舊 session
            self.sessions[username] = True
            self._save_sessions()
            return True, "登入成功"

    def logout(self, username):
        with LOCK:
            if username in self.sessions:
                self.sessions[username] = False
                self._save_sessions()
                return True, "登出成功"
            return False, "帳號不存在或未登入"

    def is_logged_in(self, username):
        return self.sessions.get(username, False)

    # ------------------------------
    # 遊玩紀錄
    # ------------------------------
    def record_play(self, username, game_name, version):
        """記錄玩家玩過的遊戲與版本"""
        with LOCK:
            accounts = self._load_accounts()
            if username not in accounts:
                return False
            if "records" not in accounts[username]:
                accounts[username]["records"] = {}
            if game_name not in accounts[username]["records"]:
                accounts[username]["records"][game_name] = []
            if version not in accounts[username]["records"][game_name]:
                accounts[username]["records"][game_name].append(version)
            self._save_accounts(accounts)
            return True

    def has_played(self, username, game_name):
        """檢查玩家是否玩過這款遊戲"""
        accounts = self._load_accounts()
        user = accounts.get(username, {})
        records = user.get("records", {})
        return game_name in records and len(records[game_name]) > 0
