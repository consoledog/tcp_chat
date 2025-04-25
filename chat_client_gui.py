import socket
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

SERVER_HOST = '127.0.0.1'    # or your server’s IP
SERVER_PORT = 5001

class ChatClientGUI:
    def __init__(self, master):
        self.master = master
        master.title("TCP Chat Client")

        # ---- Chat display ----
        self.text_area = ScrolledText(master, state='disabled', wrap='word', height=20)
        self.text_area.pack(padx=10, pady=10, fill='both', expand=True)

        # ---- Entry + Send button ----
        bottom = tk.Frame(master)
        self.entry = tk.Entry(bottom, width=50)
        self.entry.pack(side='left', padx=(0,5), fill='x', expand=True)
        self.entry.bind("<Return>", lambda e: self.send_message())
        send_btn = tk.Button(bottom, text="Send", command=self.send_message)
        send_btn.pack(side='right')
        bottom.pack(padx=10, pady=(0,10), fill='x')

        # ---- Networking setup ----
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SERVER_HOST, SERVER_PORT))

        # Ask for nickname via popup
        self.nickname = None
        self.prompt_nickname()

        # Start receiver thread
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def prompt_nickname(self):
        def on_ok():
            nick = nick_entry.get().strip()
            if nick:
                self.nickname = nick
                popup.destroy()
                self.sock.sendall(nick.encode())
        popup = tk.Toplevel(self.master)
        popup.title("Enter Nickname")
        tk.Label(popup, text="Nickname:").pack(padx=10, pady=5)
        nick_entry = tk.Entry(popup)
        nick_entry.pack(padx=10, pady=5)
        nick_entry.focus()
        tk.Button(popup, text="OK", command=on_ok).pack(pady=(0,10))
        self.master.wait_window(popup)

    def receive_loop(self):
        """Background thread: receive and display."""
        try:
            while True:
                data = self.sock.recv(1024)
                if not data:
                    break
                message = data.decode().strip()
                # schedule GUI update
                self.master.after(0, self.append_text, message)
        except OSError:
            pass
        finally:
            self.sock.close()
            self.master.after(0, self.append_text, "[Disconnected]")

    def send_message(self):
        text = self.entry.get().strip()
        if not text:
            return
        try:
            self.sock.sendall(text.encode())
        except OSError:
            self.append_text("[Error sending message]")
        self.entry.delete(0, 'end')

    def append_text(self, message: str):
        self.text_area.configure(state='normal')
        self.text_area.insert('end', message + "\n")
        self.text_area.configure(state='disabled')
        self.text_area.see('end')

if __name__ == "__main__":
    root = tk.Tk()
    client = ChatClientGUI(root)
    root.mainloop()
