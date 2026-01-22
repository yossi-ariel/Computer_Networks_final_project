import socket
import threading
import json
import queue
import tkinter as tk
from tkinter import ttk, messagebox

HOST = "127.0.0.1"
PORT = 5000


def send_json(sock, obj):
    sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))


def recv_loop(sock, q):
    try:
        file = sock.makefile("r", encoding="utf-8")
        for line in file:
            q.put(json.loads(line))
    except Exception:
        pass
    finally:
        q.put({"type": "disconnected"})


class ChatClientGUI:
    def __init__(self, root):
        self.root = root
        root.title("TCP Private Chat")
        root.geometry("800x500")

        self.sock = None
        self.queue = queue.Queue()
        self.selected_user = None
        self.conversations = {}
        self.last_users = set()

        self.build_ui()
        self.poll_queue()

    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        self.user_var = tk.StringVar()
        ttk.Label(top, text="Username:").pack(side="left")
        ttk.Entry(top, textvariable=self.user_var, width=15).pack(side="left", padx=5)
        ttk.Button(top, text="Connect", command=self.connect).pack(side="left", padx=5)

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        self.users = tk.Listbox(main, width=25)
        self.users.pack(side="left", fill="y")
        self.users.bind("<<ListboxSelect>>", self.select_user)

        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=10)

        self.chat_title = ttk.Label(right, text="Select a user")
        self.chat_title.pack(anchor="w")

        self.chat = tk.Text(right, state="disabled")
        self.chat.pack(fill="both", expand=True)

        bottom = ttk.Frame(right)
        bottom.pack(fill="x")

        self.msg_var = tk.StringVar()
        ttk.Entry(bottom, textvariable=self.msg_var).pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="Send", command=self.send).pack(side="left", padx=5)

    def connect(self):
        username = self.user_var.get().strip()
        if not username:
            messagebox.showerror("Error", "Username required")
            return

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((HOST, PORT))
        send_json(self.sock, {"type": "hello", "username": username})

        threading.Thread(
            target=recv_loop,
            args=(self.sock, self.queue),
            daemon=True
        ).start()

    def select_user(self, _):
        sel = self.users.curselection()
        if not sel:
            return
        self.selected_user = self.users.get(sel[0])
        self.chat_title.config(text=f"Private chat with {self.selected_user}")
        self.render()

    def send(self):
        if not self.selected_user:
            return

        text = self.msg_var.get().strip()
        if not text:
            return

        send_json(self.sock, {
            "type": "dm",
            "to": self.selected_user,
            "text": text
        })

        self.conversations.setdefault(self.selected_user, []).append(f"You: {text}")
        self.msg_var.set("")
        self.render()

    def render(self):
        self.chat.config(state="normal")
        self.chat.delete("1.0", "end")
        for line in self.conversations.get(self.selected_user, []):
            self.chat.insert("end", line + "\n")
        self.chat.config(state="disabled")

    def poll_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()

                if msg["type"] == "user_list":
                    new_users = set(msg["users"])

                    disconnected = self.last_users - new_users
                    for user in disconnected:
                        self.conversations.setdefault(user, []).append(
                            f"[System] {user} has disconnected."
                        )
                        if self.selected_user == user:
                            self.render()

                    self.last_users = new_users

                    self.users.delete(0, "end")
                    for u in msg["users"]:
                        self.users.insert("end", u)

                elif msg["type"] == "dm":
                    sender = msg["from"]
                    text = msg["text"]
                    self.conversations.setdefault(sender, []).append(f"{sender}: {text}")
                    if self.selected_user == sender:
                        self.render()

        except queue.Empty:
            pass

        self.root.after(100, self.poll_queue)


def main():
    root = tk.Tk()
    ChatClientGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()