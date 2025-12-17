import socket, threading, json, time, random

MAP_WIDTH, MAP_HEIGHT = 2000, 2000
TICK = 0.03
SHOT_INTERVAL = 0.5
BULLET_SPEED = 10

MAX_SPEED = 15
MIN_SHOT_INTERVAL = 0.1
EXP_PER_KILL = 20
EXP_PER_BLOCK = 5
LEVEL_UP_EXP = 100

def send_line(conn, obj):
    try:
        conn.sendall((json.dumps(obj) + "\n").encode())
    except: pass

def recv_line(conn):
    buf = b""
    while True:
        try: ch = conn.recv(1)
        except: return None
        if not ch: return None
        if ch == b"\n": break
        buf += ch
    try: return json.loads(buf.decode())
    except: return None

class GameServer:
    def __init__(self, host="0.0.0.0", port=9001, max_players=4):
        self.host = host
        self.port = port
        self.max_players = max_players
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []
        self.players = {}  # pid -> dict
        self.bullets = []
        self.blocks = []
        self.next_id = 1
        self.lock = threading.RLock()
        self.running = True

        # 初始化方塊
        for _ in range(30):
            self.blocks.append({"x": random.randint(0, MAP_WIDTH-40),
                                "y": random.randint(0, MAP_HEIGHT-40),
                                "hp": 100})

    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen(self.max_players)
        print(f"[Server] Listening {self.host}:{self.port}")

        threading.Thread(target=self.accept_loop, daemon=True).start()
        threading.Thread(target=self.update_loop, daemon=True).start()

        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            print("[Server] Shutting down...")
            self.running = False
            self.server.close()

    def accept_loop(self):
        while self.running and len(self.clients) < self.max_players:
            conn, addr = self.server.accept()
            join = recv_line(conn)
            if join is None or join.get("type") != "join":
                conn.close()
                continue
            username = join["data"].get("username", str(addr))

            with self.lock:
                pid = self.next_id
                self.next_id += 1
                team = 1 if pid % 2 == 1 else 2
                self.players[pid] = {
                    "conn": conn,
                    "username": username,
                    "x": random.randint(50, MAP_WIDTH-50),
                    "y": random.randint(50, MAP_HEIGHT-50),
                    "hp": 100,
                    "team": team,
                    "last_shot": 0
                }
                self.clients.append(conn)

            send_line(conn, {"type":"welcome","data":{"player":pid,"map_w":MAP_WIDTH,"map_h":MAP_HEIGHT}})
            print(f"[Server] {username} joined as player {pid}, team {team}")

            # 每個 client 對應一個 thread
            threading.Thread(target=self.client_loop, args=(pid, conn), daemon=True).start()

    def client_loop(self, pid, conn):
        while self.running:
            msg = recv_line(conn)
            if not msg: break
            self.handle_move(pid, msg)
        # 玩家斷線
        with self.lock:
            if pid in self.players: del self.players[pid]
            if conn in self.clients: self.clients.remove(conn)
            conn.close()
        print(f"[Server] Player {pid} disconnected")

    def handle_move(self, pid, msg):
        p = self.players.get(pid)
        if not p: 
            return

        # 初始化玩家屬性（如果還沒設定）
        if "speed" not in p:
            p["speed"] = 5          # 預設移動速度
        if "shot_interval" not in p:
            p["shot_interval"] = SHOT_INTERVAL
        if "exp" not in p:
            p["exp"] = 0
        if "level" not in p:
            p["level"] = 1

        # ------------------ 玩家移動 ------------------
        dx = msg["data"].get("dx", 0) * p["speed"] / 5  # 速度加成
        dy = msg["data"].get("dy", 0) * p["speed"] / 5
        p["x"] = max(0, min(MAP_WIDTH, p["x"] + dx))
        p["y"] = max(0, min(MAP_HEIGHT, p["y"] + dy))

        # ------------------ 玩家射擊 ------------------
        if msg["type"] == "shoot":
            now = time.time()
            if now - p["last_shot"] >= p["shot_interval"]:
                mx = msg["data"]["mx"]
                my = msg["data"]["my"]
                dx_b = (mx - p["x"]) / BULLET_SPEED
                dy_b = (my - p["y"]) / BULLET_SPEED
                self.bullets.append({
                    "x": p["x"],
                    "y": p["y"],
                    "dx": dx_b,
                    "dy": dy_b,
                    "team": p["team"],
                    "owner": pid
                })
                p["last_shot"] = now

        # ------------------ 升級判斷 ------------------

        if p["exp"] >= LEVEL_UP_EXP * p["level"]:
            p["level"] += 1
            # 玩家升級時選擇提升速度或射速
            # 這裡暫時自動選擇，可改成發訊息給客戶端選擇
            choice = random.choice(["speed", "shot"])
            if choice == "speed":
                p["speed"] = min(MAX_SPEED, p["speed"] + 1)
            else:
                p["shot_interval"] = max(MIN_SHOT_INTERVAL, p["shot_interval"] * 0.9)

    def update_loop(self):
        while self.running:
            with self.lock:
                # 移動子彈
                new_bullets = []
                for b in self.bullets:
                    b["x"] += b["dx"]
                    b["y"] += b["dy"]
                    if not (0 <= b["x"] <= MAP_WIDTH and 0 <= b["y"] <= MAP_HEIGHT):
                        continue

                    hit = False

                    # 玩家碰撞
                    for pid, p in self.players.items():
                        if p["team"] != b["team"] and abs(p["x"]-b["x"])<15 and abs(p["y"]-b["y"])<15:
                            p["hp"] -= 10
                            owner = b.get("owner")
                            if owner in self.players and p["hp"] <= 0:
                                self.players[owner]["exp"] = self.players[owner].get("exp",0) + 50
                            hit = True
                            break

                    # 方塊碰撞
                    if not hit:
                        for blk in self.blocks:
                            if abs(blk["x"]-b["x"])<20 and abs(blk["y"]-b["y"])<20:
                                blk["hp"] -= 10
                                owner = b.get("owner")
                                if owner in self.players and blk["hp"] <= 0:
                                    self.players[owner]["exp"] = self.players[owner].get("exp",0) + 10
                                hit = True
                                break

                    if not hit:
                        new_bullets.append(b)

                self.bullets = new_bullets

                # 方塊重生
                for blk in self.blocks:
                    if blk["hp"] <= 0:
                        blk["x"] = random.randint(0, MAP_WIDTH-40)
                        blk["y"] = random.randint(0, MAP_HEIGHT-40)
                        blk["hp"] = 100

                # 玩家死亡
                for pid, p in list(self.players.items()):
                    if p["hp"] <= 0:
                        try:
                            send_line(p["conn"], {"type":"dead","data":{"message":"你已死亡"}})
                        except: pass
                        if p["conn"] in self.clients:
                            self.clients.remove(p["conn"])
                        del self.players[pid]

                # 玩家經驗與升級
                for pid, p in self.players.items():
                    p["exp"] = p.get("exp",0)
                    p["level"] = p.get("level",1)
                    p["speed"] = p.get("speed",5)
                    p["shot_interval"] = p.get("shot_interval",SHOT_INTERVAL)

                    if p["exp"] >= LEVEL_UP_EXP * p["level"]:
                        p["level"] += 1
                        # 隨機升級: 移動速度或射速
                        choice = random.choice(["speed","shot"])
                        if choice=="speed":
                            p["speed"] = min(MAX_SPEED, p["speed"]+1)
                        else:
                            p["shot_interval"] = max(MIN_SHOT_INTERVAL, p["shot_interval"]*0.9)

                # 廣播狀態給所有玩家
                state = {
                    "type": "update",
                    "data": {
                        "players": {
                            pid: {
                                "x": p["x"],
                                "y": p["y"],
                                "hp": p["hp"],
                                "team": p["team"],
                                "exp": p["exp"],
                                "level": p["level"],
                                "speed": p["speed"],
                                "shot_interval": p["shot_interval"]
                            } for pid, p in self.players.items()
                        },
                        "bullets": self.bullets,
                        "blocks": self.blocks
                    }
                }
                for c in self.clients:
                    send_line(c, state)

            time.sleep(TICK)

if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9002)
    parser.add_argument("--max_players", type=int, default=4)
    args = parser.parse_args()
    gs = GameServer(host=args.host, port=args.port, max_players=args.max_players)
    gs.start()
