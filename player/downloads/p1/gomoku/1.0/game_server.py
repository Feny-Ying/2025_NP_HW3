#!/usr/bin/env python3
import socket, threading, json, argparse, time

def send_line(conn, obj):
    msg = json.dumps(obj, separators=(',', ':')) + "\n"
    conn.sendall(msg.encode('utf-8'))

def recv_line(conn):
    buf = b""
    while True:
        ch = conn.recv(1)
        if not ch:
            return None
        if ch == b"\n":
            break
        buf += ch
    try:
        return json.loads(buf.decode('utf-8'))
    except:
        return None

class GomokuServer:
    def __init__(self, host='0.0.0.0', port=9001, board_size=15, wait_seconds=30, max_players=2):
        self.host = host
        self.port = port
        self.board_size = board_size
        self.wait_seconds = wait_seconds
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []  # list of dict: {"conn", "addr", "username", "player_id"}
        self.lock = threading.RLock()
        self.running = True
        self.board = [[0]*board_size for _ in range(board_size)]
        self.turn = 1  # player id 1 or 2
        self.max_players = max_players

    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen(8)
        print(f"[GomokuServer] Listening on {self.host}:{self.port}, waiting for {self.max_players} players...")
        threading.Thread(target=self.accept_loop, daemon=True).start()

        # wait for up to wait_seconds for players
        t0 = time.time()
        while time.time() - t0 < self.wait_seconds and len(self.clients) < self.max_players:
            time.sleep(0.2)

        if len(self.clients) < 1:
            print("[GomokuServer] No players connected. Shutting down.")
            self.shutdown()
            return

        print(f"[GomokuServer] {len(self.clients)} player(s) connected. Starting game.")

        # 等 client 初始化 welcome
        time.sleep(0.5)
        players = [c["username"] for c in self.clients]
        self.broadcast({"type":"start","data":{"players":players,"first_turn":self.turn}})

        self.play_game()
        self.shutdown()

    def accept_loop(self):
        while self.running and len(self.clients) < self.max_players:
            try:
                conn, addr = self.server.accept()
                join = recv_line(conn)
                if join is None or join.get("type") != "join":
                    conn.close()
                    continue
                username = join.get("data", {}).get("username", f"{addr}")
                with self.lock:
                    player_id = len(self.clients) + 1
                    client_info = {"conn":conn, "addr":addr, "username":username, "player_id":player_id}
                    self.clients.append(client_info)
                print(f"[GomokuServer] {username} joined as player {player_id} from {addr}")
                send_line(conn, {"type":"welcome","data":{"player":player_id,"board_size":self.board_size}})
                threading.Thread(target=self.client_listener, args=(conn, addr, username, player_id), daemon=True).start()
            except Exception as e:
                print("[GomokuServer] accept error:", e)
                break

    def client_listener(self, conn, addr, username, player_id):
        try:
            while self.running:
                # 只偵測斷線，不讀任何資料
                time.sleep(1)
        finally:
            print(f"[GomokuServer] {username} (player {player_id}) disconnected")
            with self.lock:
                self.clients = [c for c in self.clients if c["player_id"] != player_id]
            try:
                conn.close()
            except:
                pass
            # 若玩家在遊戲中斷線，結束遊戲並通知其他人
            self.running = False
            self.broadcast({"type":"server_shutdown","data":{"msg":"player disconnected"}})

    def broadcast(self, obj):
        data = json.dumps(obj, separators=(',', ':')) + "\n"
        with self.lock:
            for c in list(self.clients):
                try:
                    c["conn"].sendall(data.encode('utf-8'))
                except:
                    pass

    def send_to_player(self, player_id, obj):
        data = json.dumps(obj, separators=(',', ':')) + "\n"
        with self.lock:
            for c in list(self.clients):
                if c["player_id"] == player_id:
                    try:
                        c["conn"].sendall(data.encode('utf-8'))
                        return c["conn"]
                    except:
                        return None
        return None

    def recv_from_conn(self, conn, timeout=30):
        try:
            conn.settimeout(timeout)
            msg = recv_line(conn)
            conn.settimeout(None)
            return msg
        except:
            try:
                conn.settimeout(None)
            except:
                pass
            return None

    def _close_all_clients(self):
        # 嘗試主動關閉所有 client，避免 client 卡在 recv()
        with self.lock:
            for c in list(self.clients):
                conn = c.get("conn")
                try:
                    try:
                        conn.shutdown(socket.SHUT_RDWR)
                    except:
                        pass
                    conn.close()
                except:
                    pass
            # clear list
            self.clients = []

    def play_game(self):
        total_moves = 0
        max_moves = self.board_size * self.board_size
        while self.running and total_moves < max_moves:
            # 找當前玩家
            with self.lock:
                cur = next((c for c in self.clients if c["player_id"]==self.turn), None)
            if cur is None:
                print("[GomokuServer] current player disconnected. Ending.")
                break
            conn, username = cur["conn"], cur["username"]

            try:
                send_line(conn, {"type":"prompt","data":{"msg":"your move"}})
                msg = self.recv_from_conn(conn, timeout=60)
                if msg is None:
                    print(f"[GomokuServer] no response from player {self.turn}. Ending game.")
                    break
                if msg.get("type") != "move":
                    continue
                x, y = int(msg["data"]["x"]), int(msg["data"]["y"])
            except Exception as e:
                print("[GomokuServer] error reading move:", e)
                break

            # 驗證落子
            with self.lock:
                if 0 <= x < self.board_size and 0 <= y < self.board_size:
                    if self.board[y][x] == 0:
                        self.board[y][x] = self.turn
                        total_moves += 1
                        if self.check_win(x,y,self.turn):
                            # 廣播最後一次 board + winner
                            self.broadcast({"type":"update","data":{"board":self.board,"winner":self.turn}})
                            self.broadcast({"type":"game_end","data":{"winner":self.turn,"board":self.board}})
                            print(f"[GomokuServer] Player {self.turn} ({username}) wins!")
                            # 等短暫時間讓 client 接收訊息
                            time.sleep(0.1)
                            # 主動關閉所有 client 連線，避免 client 卡在 recv()
                            self._close_all_clients()
                            self.running = False
                            return
                    else:
                        self.broadcast({"type":"update","data":{"board":self.board,"turn":self.turn,"msg":"occupied"}})
                else:
                    self.broadcast({"type":"update","data":{"board":self.board,"turn":self.turn,"msg":"invalid"}})

            # 換下一位玩家
            self.turn = 1 if self.turn==2 else 2
            self.broadcast({"type":"update","data":{"board":self.board,"turn":self.turn}})

        # 平手，廣播並關閉
        self.broadcast({"type":"game_end","data":{"winner":None,"board":self.board}})
        print("[GomokuServer] Game ended in a draw or stopped.")
        time.sleep(0.1)
        self._close_all_clients()
        self.running = False

    def check_win(self, x, y, player):
        dirs = [(1,0),(0,1),(1,1),(1,-1)]
        for dx,dy in dirs:
            count = 1
            nx, ny = x+dx, y+dy
            while 0<=nx<self.board_size and 0<=ny<self.board_size and self.board[ny][nx]==player:
                count+=1; nx+=dx; ny+=dy
            nx, ny = x-dx, y-dy
            while 0<=nx<self.board_size and 0<=ny<self.board_size and self.board[ny][nx]==player:
                count+=1; nx-=dx; ny-=dy
            if count>=5:
                return True
        return False

    def shutdown(self):
        self.running = False
        try:
            self.server.close()
        except:
            pass
        with self.lock:
            for c in list(self.clients):
                try:
                    send_line(c["conn"],{"type":"server_shutdown","data":{"msg":"server shutting down"}})
                    c["conn"].close()
                except:
                    pass
        # ensure all closed
        try:
            self._close_all_clients()
        except:
            pass

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--board_size", type=int, default=15)
    parser.add_argument("--wait", type=int, default=30)
    parser.add_argument("--max_players", type=int, default=2)
    args = parser.parse_args()

    gs = GomokuServer(host=args.host, port=args.port, board_size=args.board_size, wait_seconds=args.wait, max_players = args.max_players)
    gs.start()
