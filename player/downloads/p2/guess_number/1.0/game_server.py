#!/usr/bin/env python3
import socket, threading, json, argparse, random, time

# 簡單回合制多人遊戲 server
# Protocol: JSON lines with {"type": "...", "data": ...}

def send_line(conn, obj):
    msg = json.dumps(obj) + "\n"
    conn.sendall(msg.encode('utf-8'))

def recv_line(conn):
    # read until newline
    buf = b""
    while True:
        ch = conn.recv(1)
        if not ch:
            return None
        if ch == b"\n":
            break
        buf += ch
    return json.loads(buf.decode('utf-8'))

class GameServer:
    def __init__(self, host='0.0.0.0', port=9000, max_players=2, rounds=3):
        self.host = host
        self.port = port
        self.max_players = max_players
        self.rounds = rounds
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []  # list of (conn, addr, username)
        self.lock = threading.Lock()
        self.scores = {}  # username -> score
        self.running = True

    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen(8)
        print(f"[GameServer] Listening on {self.host}:{self.port}; waiting for {self.max_players} players")
        accept_thread = threading.Thread(target=self.accept_loop, daemon=True)
        accept_thread.start()
        # wait until enough players or timeout
        t0 = time.time()
        while len(self.clients) < self.max_players and time.time() - t0 < 30:
            time.sleep(0.5)
        if len(self.clients) < 1:
            print("No players connected; shutting down.")
            self.shutdown()
            return
        print(f"{len(self.clients)} players connected. Starting game.")
        self.broadcast({"type": "start", "data": {"players": [u for (_,_,u) in self.clients]}})
        self.play_game()
        self.shutdown()

    def accept_loop(self):
        while self.running and len(self.clients) < self.max_players:
            try:
                conn, addr = self.server.accept()
                # first message should be {"type":"join","data":{"username":"..."}} 
                join = recv_line(conn)
                if join is None or join.get("type") != "join":
                    conn.close()
                    continue
                username = join["data"].get("username", str(addr))
                with self.lock:
                    self.clients.append((conn, addr, username))
                    self.scores[username] = 0
                print(f"[GameServer] {username} joined from {addr}")
                send_line(conn, {"type":"joined","data":{"msg":"welcome"}})
            except Exception as e:
                print("accept error:", e)
                break

    def broadcast(self, obj):
        with self.lock:
            for (conn,_,_) in self.clients:
                try:
                    send_line(conn, obj)
                except:
                    pass

    def play_game(self):
        for r in range(1, self.rounds+1):
            target = random.randint(1, 10)
            self.broadcast({"type":"round_start", "data":{"round": r}})
            # collect moves in order of client list
            moves = {}
            for (conn, addr, username) in list(self.clients):
                try:
                    send_line(conn, {"type":"prompt", "data":{"msg":f"Round {r}: enter 1-10"}})
                    msg = recv_line(conn)
                    if msg is None:
                        val = None
                    else:
                        val = int(msg.get("data", {}).get("move", 0))
                    moves[username] = val
                except Exception as e:
                    print("error getting move:", e)
                    moves[username] = None
            # scoring: closest to target gets +1
            best = None
            best_diff = 999
            for u,v in moves.items():
                if v is None:
                    continue
                d = abs(v - target)
                if d < best_diff:
                    best_diff = d
                    best = u
            if best:
                self.scores[best] += 1
            self.broadcast({"type":"round_result","data":{"target":target,"moves":moves,"winner":best, "scores":self.scores}})
            time.sleep(1)
        # final
        sorted_scores = sorted(self.scores.items(), key=lambda x: -x[1])
        winners = [u for u,sc in sorted_scores if sc==sorted_scores[0][1]]
        self.broadcast({"type":"game_end","data":{"scores":self.scores,"winners":winners}})
        print("Game finished. scores:", self.scores)

    def shutdown(self):
        self.running = False
        try:
            self.server.close()
        except:
            pass
        with self.lock:
            for (conn,_,_) in self.clients:
                try:
                    conn.close()
                except:
                    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--max_players", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    gs = GameServer(host=args.host, port=args.port, max_players=args.max_players, rounds=args.rounds)
    gs.start()