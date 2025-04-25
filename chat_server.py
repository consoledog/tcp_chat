import socket
import threading
import re
from typing import Optional
from datetime import datetime
from collections import deque
import json
from colorama import init, Fore, Style

# Call this once, before any ANSI codes get emmited
init(autoreset=True)

HOST = '0.0.0.0' # Listens to all interfaces
PORT = 5001

HISTORY_FILE = "chat_history.json"
COMMANDS = [
    "/list - lists all online users",
    "/msg <send_to> <message> - send private message",
    "/nickname <nick_name> - change nickname",
    "/me <action> - just for fun, inform other users what you are doing",
    "/quit - leave the chat "
]

# Keep track of all connected client sockets
nicknames: dict[socket.socket, str] = {}
clients_lock = threading.Lock()
history = deque(maxlen=20)

# regex: allow only letters, numbers, underscores; 3–16 chars
NICK_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")

def load_history():
    """Load persisted history on server start, if present."""
    try:
        with open(HISTORY_FILE, "r") as file:
            items = json.load(file)
        for item in items[-20:]:
            history.append(item)
    except (IOError, ValueError):
        # TODO: no file or invalid JSON
        pass

def save_history():
    """Write current history to JSON file."""
    with open(HISTORY_FILE, "w") as f:
        json.dump(list(history), f, indent=2)

def broadcast(msg: str, sender: Optional[socket.socket] = None):
    """If sender is given, send to everyone *except* them.
       Otherwise send to all clients."""
    
    # Build the message
    timestamp = datetime.now().strftime("%H:%M")
    full_msg = f"[{timestamp}] {msg}"

    with clients_lock:
        history.append(full_msg)
        save_history()

        for client_sock in nicknames:
            if sender is not None and client_sock is sender:
                continue
            try:
                client_sock.sendall(full_msg.encode())
            except:
                pass

def handle_client(client_sock: socket.socket, addr: str):
    """Receive messages from a client and broadcast them"""
    
    with client_sock:
        # Read very first message as nickname
        raw = client_sock.recv(1024)
        if not raw:
            return
        nickname = raw.decode().strip()

        # Register
        with clients_lock:
            nicknames[client_sock] = nickname
        
        send_chat_history_to_user(client_sock)

        # Let everyone know they joined
        join_msg = f"{Fore.YELLOW}{nickname}{Style.RESET_ALL} has joined the chat"
        broadcast(join_msg, client_sock)
        print(f"[+] {addr} is now known as '{nickname}'")

        try:
            # Main loop is used to read chat messages and re-broadcast them
            while True:
                data = client_sock.recv(1024)
                if not data:
                    break
                text = data.decode().strip()

                if text.lower() == "/list":
                    list_online_users(client_sock)
                elif text.lower().startswith("/msg"):
                    send_private_message(client_sock, text)
                elif text.lower() == "/help":
                    send_help(client_sock)
                elif text.lower().startswith("/nick"):
                    change_nick(client_sock, text)
                elif text.lower().startswith("/me"):
                    forward_actions(client_sock, text)
                else:
                    colored_nick = f"{Fore.YELLOW}{nickname}{Style.RESET_ALL}"
                    broadcast(f"{colored_nick} says: {text}", client_sock)
        finally:
            # Cleanup on disconnect
            with clients_lock:
                del nicknames[client_sock]
            broadcast(f"{nickname} has left the chat", client_sock)
            print(f"[-] {nickname} ({addr}) disconnected")

def list_online_users(client_sock: socket.socket):
    with clients_lock:
        online_people = list(nicknames.values())
    payload = "Online users:\n" + "\n".join(online_people) + "\n"
    client_sock.sendall(payload.encode())

def send_private_message(client_sock: socket.socket, text: str):
    parts = text.split(" ", 2)

    if len(parts) == 3:
        target_nick, private_message = parts[1], parts[2]
        sender_nick = nicknames[client_sock]

        # Find the socket for the nickname
        target_socket = None
        with clients_lock:
            for socket, nickname in nicknames.items():
                if nickname == target_nick:
                    target_socket = socket
                    break
        
        if target_socket:
            # Send the message only to the target, and notify the sender
            try:
                timestamp = datetime.now().strftime("%H:%M")
                sender_nick = f"{Fore.YELLOW}{sender_nick}{Style.RESET_ALL}"
                target_nick = f"{Fore.YELLOW}{target_nick}{Style.RESET_ALL}"
                target_socket.sendall(f"[{timestamp}][PM from {sender_nick}]: {private_message}".encode())
                client_sock.sendall(f"[{timestamp}][PM to {target_nick}]: {private_message}".encode())
            except Exception:
                pass
        else:
            client_sock.sendall(f" User '{target_nick}' not found.\n".encode())
    else:
        client_sock.sendall(b"Usage: /msg <nick> <message>\n")

def send_help(client_sock: socket.socket):
    payload = "Available commands:\n" + "\n".join(COMMANDS) + "\n"
    client_sock.sendall(payload.encode())

def change_nick(client_sock: socket.socket, received_payload: str):
    """
    payload is the full command string the client sent, e.g. "/nick NewNick"
    """

    # Check is the format of the command good
    parts = received_payload.split(" ")
    if len(parts) != 2:
        client_sock.sendall(b"Usage: /nick <new_nickname>\n")
        return
    
    # Parse the new nick
    new_nick = parts[1].strip()
    
    # Validate is the nickname good
    if not NICK_RE.match(new_nick):
        client_sock.sendall(b"Invalid nickname. Use 3 to 16 chars: letters, digits, or underscores only.\n")
        return
    
    with clients_lock:
        # Check is new nick already take by other users
        if new_nick in nicknames.values():
            client_sock.sendall(f"Nickname {new_nick} is already taken \n".encode())
            return
        
        # Update nick name
        old_nick = nicknames.get(client_sock, None)
        nicknames[client_sock] = new_nick

    # Inform all users about the change
    broadcast(f"User changed nick name {old_nick} -> {new_nick}")

def forward_actions(client_sock: socket.socket, received_payload: str):
    parts = received_payload.split(" ")
    if len(parts) != 2:
        client_sock.sendall(b"Usage: /me <action>\n")
        return

    action = parts[1]
    nickname = nicknames.get(client_sock, "Unkown")
    payload = f"* {nickname} {action}\n"
    broadcast(payload, sender=client_sock)

def send_chat_history_to_user(client_sock: socket.socket):
    for past in history:
        client_sock.sendall((past + "\n").encode())
def main():
    load_history()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen()
        print(f"Chat server listening on {HOST}:{PORT}")
        while True:
            client_sock, addr = srv.accept()
            thread = threading.Thread(target=handle_client, 
                                      args=(client_sock, addr),
                                      daemon=True)
            thread.start()

if __name__ == "__main__":
    main()