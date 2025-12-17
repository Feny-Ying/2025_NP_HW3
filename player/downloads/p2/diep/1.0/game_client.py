#!/usr/bin/env python3
import socket, json, threading, pygame, argparse, time, sys

# ----------------- 通訊函數 -----------------
def send_line(sock, obj):
    try:
        sock.sendall((json.dumps(obj) + "\n").encode())
    except: pass

def recv_line(sock):
    buf = b""
    while True:
        ch = sock.recv(1)
        if not ch: return None
        if ch == b"\n": break
        buf += ch
    try:
        return json.loads(buf.decode())
    except: return None

# ----------------- 客戶端類別 -----------------
class GameClient:
    def __init__(self, host, port, username, retry=5, delay=0.5):
        self.host = host
        self.port = port

        # 嘗試連線
        for attempt in range(1, retry+1):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
                print(f"[client] Connected to server at {host}:{port}")
                break
            except Exception as e:
                print(f"[client] Connection attempt {attempt} failed: {e}")
                if attempt == retry:
                    print("[client] Could not connect to server. Exiting.")
                    sys.exit(1)
                time.sleep(delay)

        # 送 join 訊息
        send_line(self.sock, {"type":"join","data":{"username":username}})

        # 初始化資料
        self.player_id = None
        self.players = {}
        self.bullets = []
        self.blocks = []
        self.map_w, self.map_h = 2000, 2000

        # Pygame 初始化
        pygame.init()
        self.screen_w, self.screen_h = 800, 600
        self.screen = pygame.display.set_mode((self.screen_w, self.screen_h))
        pygame.display.set_caption(username)
        self.clock = pygame.time.Clock()
        self.cam_x, self.cam_y = 0, 0
        self.running = True

        # 啟動接收 thread
        threading.Thread(target=self.recv_loop, daemon=True).start()
        self.main_loop()

    # ----------------- 接收訊息 -----------------
    def recv_loop(self):
        while self.running:
            msg = recv_line(self.sock)
            if not msg:
                break
            if msg["type"] == "welcome":
                self.player_id = msg["data"]["player"]
                self.map_w = msg["data"]["map_w"]
                self.map_h = msg["data"]["map_h"]
                print(f"[client] Welcome! Player id = {self.player_id}")
            elif msg["type"] == "update":
                # 將 players 的 key 轉成 int，避免字串/整數不一致
                self.players = {int(pid): p for pid, p in msg["data"]["players"].items()}
                self.bullets = msg["data"]["bullets"]
                self.blocks = msg["data"]["blocks"]
            elif msg["type"] == "dead":
                print(msg["data"].get("message", "You are dead."))
                self.running = False
                try:
                    self.sock.close()
                except:
                    pass
                break

    # ----------------- 攝影機跟隨 -----------------
    def update_camera(self):
        # 確認 player_id 在 players 裡
        if getattr(self, 'player_id', None) is None or self.player_id not in self.players:
            return

        px = self.players[self.player_id]["x"]
        py = self.players[self.player_id]["y"]
        
        # 將攝影機置中玩家
        self.cam_x = px - self.screen_w // 2
        self.cam_y = py - self.screen_h // 2
        
        # 限制攝影機不要超出地圖邊界
        self.cam_x = max(0, min(self.cam_x, self.map_w - self.screen_w))
        self.cam_y = max(0, min(self.cam_y, self.map_h - self.screen_h))

        # debug
        #print(f"cam_x={self.cam_x}, cam_y={self.cam_y}, player_x={px}, player_y={py}")

    # ----------------- 主迴圈 -----------------
    def main_loop(self):
        while self.running:
            dt = self.clock.tick(60) / 1000
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False

            #print("start main loop")

            # ----------------- 玩家操作 -----------------
            #print(self.player_id)
            #print(self.players)
            if self.player_id in self.players:
                dx = dy = 0
                keys = pygame.key.get_pressed()
                if keys[pygame.K_w]: dy = -5
                if keys[pygame.K_s]: dy = 5
                if keys[pygame.K_a]: dx = -5
                if keys[pygame.K_d]: dx = 5
                if dx != 0 or dy != 0:
                    send_line(self.sock, {"type":"move", "data":{"dx":dx, "dy":dy}})

                #print(f"action {dx},{dy}")

                # 射擊
                if pygame.mouse.get_pressed()[0]:
                    mx, my = pygame.mouse.get_pos()
                    mx += self.cam_x
                    my += self.cam_y
                    send_line(self.sock, {"type":"shoot", "data":{"mx":mx, "my":my}})

            # 更新攝影機
            self.update_camera()
            #print("update_camera")
            # 畫面
            self.draw()
            #print("draw")

    # ----------------- 畫面 -----------------
    def draw(self):
        self.screen.fill((30,30,30))
        # 畫方塊
        for blk in self.blocks:
            pygame.draw.rect(self.screen,(0,255,0),
                            pygame.Rect(blk["x"]-self.cam_x,blk["y"]-self.cam_y,20,20))
        # 畫子彈
        for b in self.bullets:
            pygame.draw.circle(self.screen,(255,0,0),(int(b["x"]-self.cam_x),int(b["y"]-self.cam_y)),5)
        # 畫玩家
        for pid,p in self.players.items():
            color=(0,0,255) if p["team"]==1 else (255,165,0)
            pygame.draw.rect(self.screen,color,pygame.Rect(p["x"]-self.cam_x-10,p["y"]-self.cam_y-10,20,20))
        # 畫分數板
        font = pygame.font.SysFont(None, 24)
        y_offset = 10
        font = pygame.font.SysFont(None, 24)
        for pid, p in self.players.items():
            color = (0,0,255) if p["team"]==1 else (255,165,0)
            pygame.draw.rect(self.screen, color, pygame.Rect(p["x"]-self.cam_x-10, p["y"]-self.cam_y-10, 20, 20))
            
            # 等級與經驗
            level = p.get("level", 1)
            exp = p.get("exp", 0)
            text = font.render(f"L{level} EXP:{exp}", True, (255,255,255))
            self.screen.blit(text, (p["x"]-self.cam_x-10, p["y"]-self.cam_y-25))
        pygame.display.flip()

# ----------------- 主程式 -----------------
if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9002)
    parser.add_argument("--username", default="p1")
    args = parser.parse_args()
    GameClient(args.host, args.port, args.username)
