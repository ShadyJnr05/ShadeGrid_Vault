from flask import Flask, render_template, session, request, redirect, url_for, flash, Response
from socket_bridge import get_connection, send_and_recv, close_connection, HOST, PORT
from Network_utils import recv_exact

app = Flask(__name__)

# Needed for Flask's session cookie (used to remember each visitor's client_id
# and any flashed messages). In a real deployment this would be a long random
# secret kept out of source control — fine as a fixed string for a school project.
app.secret_key = "ntp-project-dev-key"


@app.route("/")
def home():
    try:
        # This either reuses this browser's existing connection, or opens
        # a brand new one if they've never visited before.
        get_connection(session)
        connected = True
    except (ConnectionRefusedError, OSError):
        connected = False

    return render_template(
        "home.html",
        connected=connected,
        host=HOST,
        port=PORT,
        username=session.get("username"),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        sock = get_connection(session)
        send_and_recv(sock, "LOGIN")            # server replies "Enter a username:"
        send_and_recv(sock, username)            # server replies "Enter a password:"
        result = send_and_recv(sock, password)   # server replies success/failure message

        flash(result)

        if result == "Login successful.":
            # The socket connection is already authenticated as this user
            # on the server's side — we just remember their name for display.
            session["username"] = username
            return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        sock = get_connection(session)
        send_and_recv(sock, "REGISTER")
        send_and_recv(sock, username)
        result = send_and_recv(sock, password)

        flash(result)

        if result.startswith("Registration successful"):
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    sock = get_connection(session)
    sock.send("LIST".encode())
    listing_raw = sock.recv(4096).decode()

    files = []
    if listing_raw not in ("EMPTY", "You must log in first."):
        for line in listing_raw.split("\n"):
            stored_name, filename, owner, visibility = line.split("|")
            files.append({
                "stored_name": stored_name,
                "filename": filename,
                "owner": owner,
                "visibility": visibility,
            })

    return render_template("dashboard.html", files=files, username=session["username"])


@app.route("/upload", methods=["POST"])
def upload():
    if "username" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    uploaded_file = request.files.get("file")
    visibility = request.form.get("visibility", "private")

    if not uploaded_file or uploaded_file.filename == "":
        flash("No file selected.")
        return redirect(url_for("dashboard"))

    file_bytes = uploaded_file.read()
    filename = uploaded_file.filename

    sock = get_connection(session)
    sock.send("UPLOAD".encode())
    sock.recv(1024)  # first "READY" — clear to send the header

    header = f"{filename}|{visibility}|{len(file_bytes)}"
    sock.send(header.encode())
    sock.recv(1024)  # second "READY" — clear to start streaming raw bytes

    sock.sendall(file_bytes)
    result = sock.recv(1024).decode()

    flash(result)
    return redirect(url_for("dashboard"))


@app.route("/download/<stored_name>")
def download(stored_name):
    if "username" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    sock = get_connection(session)
    sock.send("DOWNLOAD".encode())
    sock.recv(1024)  # "Enter the stored filename..." prompt — we don't need the text

    sock.send(stored_name.encode())
    response = sock.recv(1024).decode()
    status, _, payload = response.partition("|")

    if status == "ERROR":
        flash(payload)
        return redirect(url_for("dashboard"))

    file_size = int(payload)
    sock.send("READY".encode())
    file_bytes = recv_exact(sock, file_size)

    # Response with a Content-Disposition header tells the browser to
    # download the bytes as a file, instead of trying to display them.
    return Response(
        file_bytes,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={stored_name}"},
    )


@app.route("/logout")
def logout():
    close_connection(session)
    session.pop("username", None)
    session.pop("client_id", None)
    flash("Logged out.")
    return redirect(url_for("home"))


if __name__ == "__main__":
    # debug=True auto-reloads on code changes and shows errors in the browser —
    # very handy while building, but you'd turn it off for a real deployment.
    app.run(debug=True, port=5000)