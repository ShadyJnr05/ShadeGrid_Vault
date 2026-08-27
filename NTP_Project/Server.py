import socket
from User import register_user, login_user
from Filestore import FileStore
from Network_utils import recv_exact

HOST = "127.0.0.1"   # localhost — server only accepts connections from this same machine for now
PORT = 5050           # arbitrary port number above 1024 (ports below that need admin rights)

def handle_client(client_socket, file_store):
    # Tracks which user (if any) has successfully logged in on THIS connection.
    # We'll use this in the next step to gate upload/download access.
    logged_in_user = None

    # Keep talking to this ONE client until they disconnect or quit.
    while True:
        # recv() blocks until data arrives. Data arrives as bytes, so we .decode() it.
        command = client_socket.recv(1024).decode().strip()

        # When a client closes its socket, recv() doesn't raise an error —
        # it just returns an empty string. That's our signal to stop looping.
        if not command:
            print("[SERVER] Client disconnected.")
            break

        command = command.upper()
        print(f"[SERVER] Received command: {command}")

        if command == "QUIT":
            print("[SERVER] Client requested to quit.")
            break

        elif command == "REGISTER":
            # Ask for a username, then wait for the client's reply.
            client_socket.send("Enter a username:".encode())
            username = client_socket.recv(1024).decode().strip()

            # Ask for a password, then wait for the client's reply.
            client_socket.send("Enter a password:".encode())
            password = client_socket.recv(1024).decode().strip()

            # register_user() does the real work: strength check, hashing, saving.
            # It returns (True/False, message) so we can report back either way.
            success, message = register_user(username, password)
            print(f"[SERVER] Registration for '{username}': {message}")
            client_socket.send(message.encode())

        elif command == "LOGIN":
            client_socket.send("Enter a username:".encode())
            username = client_socket.recv(1024).decode().strip()

            client_socket.send("Enter a password:".encode())
            password = client_socket.recv(1024).decode().strip()

            success, message = login_user(username, password)
            print(f"[SERVER] Login attempt for '{username}': {message}")

            if success:
                logged_in_user = username

            client_socket.send(message.encode())

        elif command == "LIST":
            if logged_in_user is None:
                client_socket.send("You must log in first.".encode())
                continue

            files = file_store.list_available(logged_in_user)
            if not files:
                listing = "EMPTY"
            else:
                # Pipe-delimited, one file per line — easy for any client
                # (terminal or web) to split() apart and format however it wants.
                lines = [
                    f"{stored_name}|{filename}|{owner}|{visibility}"
                    for stored_name, filename, owner, visibility in files
                ]
                listing = "\n".join(lines)

            client_socket.send(listing.encode())

        elif command == "UPLOAD":
            if logged_in_user is None:
                client_socket.send("You must log in first.".encode())
                continue

            # "READY" here just tells the client it's clear to send the upload header.
            client_socket.send("READY".encode())

            # Header format: filename|visibility|size — one small text message
            # describing what's about to come, before we switch to raw bytes.
            header = client_socket.recv(1024).decode().strip()
            filename, visibility, size_str = header.split("|")
            file_size = int(size_str)

            # Second "READY" tells the client we're set up to start receiving
            # the actual file bytes now.
            client_socket.send("READY".encode())
            file_bytes = recv_exact(client_socket, file_size)

            success, message = file_store.upload(logged_in_user, filename, file_bytes, visibility)
            print(f"[SERVER] Upload from '{logged_in_user}': {message}")
            client_socket.send(message.encode())

        elif command == "DOWNLOAD":
            if logged_in_user is None:
                client_socket.send("You must log in first.".encode())
                continue

            client_socket.send("Enter the stored filename (from LIST):".encode())
            stored_name = client_socket.recv(1024).decode().strip()

            success, message, file_bytes = file_store.download(logged_in_user, stored_name)

            if not success:
                client_socket.send(f"ERROR|{message}".encode())
                continue

            # Tell the client how many bytes are coming, then wait for its
            # "READY" before streaming — otherwise the size message and the
            # raw file bytes could get jumbled together on a fast connection.
            client_socket.send(f"OK|{len(file_bytes)}".encode())
            client_socket.recv(1024)

            client_socket.sendall(file_bytes)
            print(f"[SERVER] Sent '{stored_name}' to '{logged_in_user}'.")

        else:
            client_socket.send("Unknown command.".encode())

    client_socket.close()


def start_server():
    # AF_INET  -> we're using IPv4 addresses
    # SOCK_STREAM -> we're using TCP (reliable, ordered delivery) instead of UDP
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Without this, restarting the server quickly after stopping it can throw
    # "Address already in use" because the OS hasn't released the port yet.
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((HOST, PORT))   # attach the socket to an address + port
    server_socket.listen(1)            # start listening, allow 1 queued connection for now
    print(f"[SERVER] Listening on {HOST}:{PORT}...")

    # One FileStore, created once when the server starts, shared across
    # every client that connects for as long as the server keeps running.
    file_store = FileStore()

    # Keep accepting new clients forever, instead of quitting after the first one.
    # This server handles ONE client at a time (accept() blocks until the
    # current client disconnects before it'll accept the next), which is fine
    # for a single-user demo, but worth knowing as a limitation.
    while True:
        # accept() blocks (pauses the program) until a client connects.
        # It returns a NEW socket object just for talking to that client,
        # plus the client's address (ip, port).
        client_socket, client_address = server_socket.accept()
        print(f"[SERVER] Connection established with {client_address}")

        handle_client(client_socket, file_store)

if __name__ == "__main__":
    start_server()