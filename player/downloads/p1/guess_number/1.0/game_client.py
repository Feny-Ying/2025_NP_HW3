#!/usr/bin/env python3
import socket, json, argparse, threading, sys

def send_line(s, obj):
    s.sendall((json.dumps(obj)+"\n").encode('utf-8'))

def recv_line(s):
    buf = b""
    while True:
        ch = s.recv(1)
        if not ch:
            return None
        if ch == b"\n":
            break
        buf += ch
    return json.loads(buf.decode('utf-8'))

def listen_loop(s):
    while True:
        msg = recv_line(s)
        if msg is None:
            print("[client] disconnected from server")
            break
        typ = msg.get("type")
        data = msg.get("data", {})
        if typ == "start":
            print("[game] started. players:", data.get("players"))
        elif typ == "prompt":
            prompt = data.get("msg","your move")
            while True:
                try:
                    move = int(input(prompt + " > "))
                    break
                except:
                    print("請輸入數字")
            send_line(s, {"type":"move","data":{"move": move}})
        elif typ == "round_result":
            print(f"Round result: target={data.get('target')}, moves={data.get('moves')}, winner={data.get('winner')}")
            print("Scores:", data.get("scores"))
        elif typ == "game_end":
            print("Game ended. final scores:", data.get("scores"), " winners:", data.get("winners"))
            break
        else:
            print("msg:", msg)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--username", type=str, default="p1")
    args = parser.parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((args.host, args.port))
    # send join
    send_line(s, {"type":"join","data":{"username": args.username}})
    # start listening loop (main thread reads prompts via input)
    listen_loop(s)
    s.close()
