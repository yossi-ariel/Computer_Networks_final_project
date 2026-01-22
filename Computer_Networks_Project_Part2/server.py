import socket
import threading
import json
from typing import Dict, Tuple

HOST = "0.0.0.0"
PORT = 5000

clients: Dict[str, socket.socket] = {}
lock = threading.Lock()


def send_json(conn: socket.socket, obj: dict):
    data = (json.dumps(obj) + "\n").encode("utf-8")
    conn.sendall(data)


def safe_close(conn: socket.socket):
    try:
        conn.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass


def broadcast_user_list():
    with lock:
        users = list(clients.keys())
        conns = list(clients.values())

    msg = {"type": "user_list", "users": users}
    for c in conns:
        try:
            send_json(c, msg)
        except Exception:
            pass


def remove_client(username: str):
    with lock:
        conn = clients.pop(username, None)

    if conn:
        safe_close(conn)

    print(f"[SERVER] User '{username}' disconnected")
    broadcast_user_list()


def handle_client(conn: socket.socket, addr: Tuple[str, int]):
    username = None
    print(f"[SERVER] New connection from {addr[0]}:{addr[1]}")

    try:
        file = conn.makefile("r", encoding="utf-8")

        hello = json.loads(file.readline())
        username = hello.get("username")

        if not username:
            send_json(conn, {"type": "error", "message": "Username required"})
            return

        with lock:
            if username in clients:
                send_json(conn, {"type": "error", "message": "Username already taken"})
                return
            clients[username] = conn

        print(f"[SERVER] User '{username}' connected")
        send_json(conn, {"type": "hello_ok"})
        broadcast_user_list()

        for line in file:
            msg = json.loads(line)

            if msg.get("type") == "dm":
                to_user = msg.get("to")
                text = msg.get("text")

                with lock:
                    dst = clients.get(to_user)

                if dst:
                    send_json(dst, {
                        "type": "dm",
                        "from": username,
                        "text": text
                    })
                else:
                    send_json(conn, {
                        "type": "error",
                        "message": f"User '{to_user}' is not online"
                    })

            elif msg.get("type") == "disconnect":
                break

    except Exception:
        pass
    finally:
        if username:
            remove_client(username)
        else:
            safe_close(conn)


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)

    print(f"[SERVER] Listening on {HOST}:{PORT}")

    try:
        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            ).start()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down")
    finally:
        server.close()


if __name__ == "__main__":
    main()
