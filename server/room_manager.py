import json
import os
from threading import RLock

ROOM_FILE = "rooms.json"
LOCK = RLock()

class RoomManager:
    def __init__(self):
        # 若檔案不存在 → 建立空字典
        if not os.path.exists(ROOM_FILE):
            with open(ROOM_FILE, "w") as f:
                json.dump({}, f, indent=2)

        # 讀取現有房間資料
        with open(ROOM_FILE, "r") as f:
            self.rooms = json.load(f)

    def _save(self):
        with LOCK:
            with open(ROOM_FILE, "w") as f:
                json.dump(self.rooms, f, indent=2)

    # -------------------------------
    # 房間操作
    # -------------------------------

    def create_room(self, room_id, game_name, version, host, maxplayers):
        with LOCK:
            if room_id in self.rooms:
                return False, "房間已存在"

            game_server_path = f"uploaded_games/{game_name}/{version}/game_server.py"

            self.rooms[room_id] = {
                "room_id": room_id,
                "game_name": game_name,
                "version": version,
                "game_server_path": game_server_path,
                "host": host,
                "players": [host],
                "status": "waiting",     # waiting / running / finished
                "host_addr": None,
                "host_port": None,
                "max_players": maxplayers
            }

            self._save()
            return True, "建立成功"

    def join_room(self, room_id, username):
        with LOCK:
            if room_id not in self.rooms:
                return False, "房間不存在"

            if username in self.rooms[room_id]["players"]:
                return False, "已在房間內"

            self.rooms[room_id]["players"].append(username)
            self._save()
            return True, "加入成功"

    def leave_room(self, username):
        """玩家離開房間，若房主離開則自動轉讓，房間無人時刪除"""
        with LOCK:
            room_id, room = self.get_room_of_player(username)
            if not room:
                return False, "玩家不在任何房間"

            # 移除玩家
            self.remove_player_from_room(room_id, username)

            # 若房間空了 → 刪除
            if len(room["players"]) == 0:
                del self.rooms[room_id]
                self._save()
                return True, f"房間 {room_id} 已無玩家，自動刪除"

            # 若房主離開 → 轉讓給第一位玩家
            if room["host"] == username:
                room["host"] = room["players"][0]
                self._save()
                return True, f"房主已離開，轉讓給 {room['host']}"

            self._save()
            return True, "離開房間成功"

    def remove_player_from_room(self, room_id, username):
        """內部使用，安全移除玩家"""
        if room_id not in self.rooms:
            return
        if username in self.rooms[room_id]["players"]:
            self.rooms[room_id]["players"].remove(username)

    def get_room_of_player(self, username):
        for room_id, data in self.rooms.items():
            if username in data["players"]:
                return room_id, data
        return None, None
    
    def get_rooms(self):
        return self.rooms
    
    def get_room(self, room_id):
        return self.rooms.get(room_id)
    
    def delete_room(self, room_id):
        if room_id in self.rooms:
            del self.rooms[room_id]
            self._save()
            return True
        return False
