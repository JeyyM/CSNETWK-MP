import socket
import time

PORT = 50999
BROADCAST_IP = '<broadcast>'

def build_ping(user_id):
    return f"TYPE: PING\nUSER_ID: {user_id}\n\n"

def send_ping(user_id, interval=300, verbose=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        msg = build_ping(user_id)
        sock.sendto(msg.encode("utf-8"), (BROADCAST_IP, PORT))
        if verbose:
            print(f"> SENT PING from {user_id}")
        time.sleep(interval)
