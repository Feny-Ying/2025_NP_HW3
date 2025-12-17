#!/usr/bin/env python3
import socket, json, argparse, threading, tkinter as tk, sys

def send_line(s, obj):
    s.sendall((json.dumps(obj, separators=(',', ':')) + "\n").encode('utf-8'))

def recv_line(s):
    buf = b""
    while True:
        ch = s.recv(1)
        if not ch:
            return None
        if ch == b"\n":
            break
        buf += ch
    try:
        return json.loads(buf.decode('utf-8'))
    except:
        return None


class GomokuClient:
    def __init__(self, host, port, username, cell=30, margin=20):
        self.host = host
        self.port = port
        self.username = username

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player = None
        self.board_size = 15
        self.board = [[0]*self.board_size for _ in range(self.board_size)]
        self.turn = None
        self.my_turn = False
        
        self.cell = cell
        self.margin = margin
        self.running = True  # <-- 控制 listener loop

        # GUI
        self.root = tk.Tk()
        self.root.title(f"Gomoku - {self.username}")

        canvas_size = margin*2 + cell*self.board_size
        self.canvas = tk.Canvas(self.root, width=canvas_size, height=canvas_size, bg='bisque')
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)

        self.status_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.status_var).pack()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Connect
        try:
            self.sock.connect((self.host, self.port))
        except Exception as e:
            print("Unable to connect:", e)
            sys.exit(1)

        send_line(self.sock, {"type":"join","data":{"username": self.username}})

        # Start listener thread
        threading.Thread(target=self.recv_loop, daemon=True).start()


    # ----------------------------
    # Network receive loop
    # ----------------------------
    def recv_loop(self):
        while self.running:
            msg = recv_line(self.sock)
            if msg is None:
                print("[client] disconnected from server")
                self.status_var.set("Disconnected")
                break

            typ = msg.get("type")
            data = msg.get("data", {})

            # --- welcome
            if typ == "welcome":
                self.player = data.get("player")
                size = data.get("board_size")
                if size:
                    self.board_size = size
                    self.board = [[0]*size for _ in range(size)]
                    canvas_size = self.margin*2 + self.cell*self.board_size
                    self.canvas.config(width=canvas_size, height=canvas_size)

                self.status_var.set(f"Connected. You are player {self.player}")
                self.redraw()

            # --- start
            elif typ == "start":
                players = data.get("players", [])
                first_turn = data.get("first_turn")
                self.turn = first_turn
                self.status_var.set(f"Game start! Players: {players}, First turn: {self.turn}")
                self.redraw()

            # --- prompt: it's your turn
            elif typ == "prompt":
                self.my_turn = True
                self.status_var.set("Your turn - click a cell")

            # --- update
            elif typ == "update":
                board = data.get("board")
                if board:
                    self.board = board

                winner = data.get("winner")
                self.turn = data.get("turn", self.turn)

                if winner is not None:
                    if winner == self.player:
                        self.status_var.set("You win!")
                    else:
                        self.status_var.set(f"Player {winner} wins.")
                    self.my_turn = False
                else:
                    self.status_var.set(f"Turn: {self.turn}")

                self.redraw()

            # --- game_end
            elif typ == "game_end":
                winner = data.get("winner")
                if winner is None:
                    self.status_var.set("Draw.")
                else:
                    if winner == self.player:
                        self.status_var.set("You win!")
                    else:
                        self.status_var.set(f"Player {winner} wins.")

                self.my_turn = False
                self.redraw()

                # 優雅關閉
                self.running = False
                self.root.after(500, self.graceful_shutdown)

            # --- server shutting down
            elif typ == "server_shutdown":
                self.status_var.set("Server shutdown")
                self.running = False
                self.root.after(500, self.graceful_shutdown)
                break

        try: self.sock.close()
        except: pass

    # ----------------------------
    # Graceful shutdown
    # ----------------------------
    def graceful_shutdown(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            self.sock.close()
        except:
            pass
        self.root.destroy()


    # ----------------------------
    # On click
    # ----------------------------
    def on_click(self, event):
        print("[DEBUG] click:", event.x, event.y, "my_turn=", self.my_turn)
        if not self.my_turn or self.player is None:
            return

        # 找距離最近的空格(修正版)
        closest_dist = float('inf')
        closest_col = None
        closest_row = None

        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] != 0:
                    continue

                cx = self.margin + c*self.cell
                cy = self.margin + r*self.cell
                dist = ((event.x - cx)**2 + (event.y - cy)**2)**0.5

                if dist < closest_dist:
                    closest_dist = dist
                    closest_col = c
                    closest_row = r

        if closest_col is None or closest_row is None:
            return

        # 寄送落子
        send_line(self.sock, {
            "type": "move",
            "data": {"x": closest_col, "y": closest_row}
        })

        self.my_turn = False
        self.status_var.set("Move sent. Waiting...")


    # ----------------------------
    # Draw board
    # ----------------------------
    def redraw(self):
        self.canvas.delete("all")

        size = self.board_size

        # draw grid
        for i in range(size):
            x = self.margin + i*self.cell
            self.canvas.create_line(x, self.margin,
                                    x, self.margin + (size-1)*self.cell)

            y = self.margin + i*self.cell
            self.canvas.create_line(self.margin, y,
                                    self.margin + (size-1)*self.cell, y)

        # draw pieces
        for r in range(size):
            for c in range(size):
                v = self.board[r][c]
                if v != 0:
                    cx = self.margin + c*self.cell
                    cy = self.margin + r*self.cell
                    radius = self.cell//2 - 2
                    color = "black" if v == 1 else "white"
                    self.canvas.create_oval(cx-radius, cy-radius,
                                            cx+radius, cy+radius,
                                            fill=color)

        # Text
        self.canvas.create_text(
            5, 5,
            anchor="nw",
            text=f"You={self.player}  Turn={self.turn}"
        )


    def on_close(self):
        self.running = False
        try:
            self.sock.close()
        except:
            pass
        self.root.destroy()


# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--username", default="p1")
    args = parser.parse_args()

    client = GomokuClient(args.host, args.port, args.username)
    client.root.mainloop()
