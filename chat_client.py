import socket
import threading
import sys

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5001

def receive_messages(sock: socket.socket):
    """Continouslu receive and print messages from the server."""
    while True:
        data = sock.recv(1024)
        if not data:
            print("Disconnected from server")
            sys.exit()
        print(data.decode().strip())

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((SERVER_HOST, SERVER_PORT))
        print(f"Connected to chat at {SERVER_HOST}:{SERVER_PORT}")

        # Prompt the user for his nickname and send it immediately
        nickname = input("Enter your nickname: ").strip()
        sock.sendall(nickname.encode())

        # Start receiveing thread
        thread = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
        thread.start()

        # Main thread: read user input and send
        while True:
            msg = input("")
            
            if msg.lower() == '/quit':
                print("Exiting...")
                break
            sock.sendall(msg.encode())
        
if __name__ == "__main__":
    main()