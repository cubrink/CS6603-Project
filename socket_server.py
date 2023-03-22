import socket

HOST = "192.168.0.68" 
PORT = 65432  # Port to listen on (non-privileged ports are > 1023)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    # https://stackoverflow.com/a/33036387
    s.bind(("", PORT))
    s.listen()
    conn, addr = s.accept()
    with conn:
        print(f"Connected by {addr}")
        while True:
            data = conn.recv(1024)
            confirm_msg = b"Received: " + data
            if data:
                conn.sendall(confirm_msg)
                print(confirm_msg.decode("utf-8"))
