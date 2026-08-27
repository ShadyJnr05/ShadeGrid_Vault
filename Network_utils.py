def recv_exact(sock, num_bytes):
    """Keep calling recv() until we've collected exactly num_bytes bytes.

    TCP is a stream of bytes, not a stream of "messages" — a single recv()
    call can return fewer bytes than you asked for, especially for larger
    amounts of data. So instead of trusting one recv() call, we keep
    reading into a buffer until we've got everything we expect.
    """
    data = b""
    while len(data) < num_bytes:
        chunk = sock.recv(min(4096, num_bytes - len(data)))
        if not chunk:
            # The connection closed before we got everything we expected.
            break
        data += chunk
    return data