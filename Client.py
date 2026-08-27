import socket
import os
from network_utils import recv_exact

HOST = "127.0.0.1"   # must match the server's address
PORT = 5050           # must match the server's port

def start_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # connect() reaches out to the server's bind() address.
    # This is what actually triggers the server's accept() to return.
    client_socket.connect((HOST, PORT))
    print(f"[CLIENT] Connected to {HOST}:{PORT}")

    while True:
        command = input("\nType REGISTER, LOGIN, LIST, UPLOAD, DOWNLOAD, or QUIT: ").strip().upper()

        # Send the command — must be bytes, so we .encode() the string.
        client_socket.send(command.encode())

        if command == "QUIT":
            print("[CLIENT] Closing connection.")
            break

        elif command in ("REGISTER", "LOGIN"):
            # Server will prompt us for a username, then a password.
            # Each recv() here matches one send() on the server's side.
            prompt = client_socket.recv(1024).decode()
            username = input(f"{prompt} ")
            client_socket.send(username.encode())

            prompt = client_socket.recv(1024).decode()
            password = input(f"{prompt} ")
            client_socket.send(password.encode())

            result = client_socket.recv(1024).decode()
            print(f"[CLIENT] {result}")

        elif command == "LIST":
            listing = client_socket.recv(4096).decode()

            if listing == "You must log in first.":
                print(f"[CLIENT] {listing}")
            elif listing == "EMPTY":
                print("[CLIENT] No files available.")
            else:
                print("[CLIENT]")
                for line in listing.split("\n"):
                    stored_name, filename, owner, visibility = line.split("|")
                    print(f"  {stored_name} | {filename} ({visibility}, owner: {owner})")

        elif command == "UPLOAD":
            ack = client_socket.recv(1024).decode()
            if ack == "You must log in first.":
                print(f"[CLIENT] {ack}")
                continue

            local_path = input("Path to the file you want to upload: ").strip()
            if not os.path.isfile(local_path):
                print("[CLIENT] That file doesn't exist on disk.")
                continue

            visibility = input("Public or private? ").strip().lower()
            if visibility not in ("public", "private"):
                print("[CLIENT] Visibility must be 'public' or 'private'.")
                continue

            with open(local_path, "rb") as f:
                file_bytes = f.read()

            filename = os.path.basename(local_path)

            # Send the small text header first: what the file is called,
            # who can see it, and how many bytes are coming.
            header = f"{filename}|{visibility}|{len(file_bytes)}"
            client_socket.send(header.encode())

            # Wait for the server's "READY" before streaming raw bytes.
            client_socket.recv(1024)
            client_socket.sendall(file_bytes)

            result = client_socket.recv(1024).decode()
            print(f"[CLIENT] {result}")

        elif command == "DOWNLOAD":
            prompt = client_socket.recv(1024).decode()
            if prompt == "You must log in first.":
                print(f"[CLIENT] {prompt}")
                continue

            stored_name = input(f"{prompt} ").strip()
            client_socket.send(stored_name.encode())

            response = client_socket.recv(1024).decode()
            status, _, payload = response.partition("|")

            if status == "ERROR":
                print(f"[CLIENT] {payload}")
                continue

            file_size = int(payload)
            client_socket.send("READY".encode())

            file_bytes = recv_exact(client_socket, file_size)

            os.makedirs("downloads", exist_ok=True)
            save_path = os.path.join("downloads", stored_name)
            with open(save_path, "wb") as f:
                f.write(file_bytes)

            print(f"[CLIENT] Downloaded and saved to {save_path}")

        else:
            response = client_socket.recv(1024).decode()
            print(f"[CLIENT] {response}")

    client_socket.close()

if __name__ == "__main__":
    start_client()