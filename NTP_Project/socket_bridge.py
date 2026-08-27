import socket
import uuid

HOST = "127.0.0.1"
PORT = 5050

# Every browser visitor gets a random ID stored in their session cookie.
# We use that ID as the key here to remember THEIR socket connection,
# separately from anyone else visiting the site at the same time.
active_connections = {}


def get_connection(session):
    """Return this browser's existing socket connection to server.py,
    opening a new one only if it doesn't have one yet."""
    if "client_id" not in session:
        session["client_id"] = str(uuid.uuid4())

    client_id = session["client_id"]

    if client_id not in active_connections:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        active_connections[client_id] = sock

    return active_connections[client_id]


def send_and_recv(sock, message):
    """Send one message and return the server's single reply.
    Matches the request/reply rhythm server.py's protocol expects."""
    sock.send(message.encode())
    return sock.recv(1024).decode()


def close_connection(session):
    """Close and forget this browser's connection (e.g. on logout)."""
    client_id = session.get("client_id")
    if client_id and client_id in active_connections:
        active_connections[client_id].close()
        del active_connections[client_id]