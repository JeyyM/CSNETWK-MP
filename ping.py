import socket
import time
import struct

PORT = 50999

def get_broadcast_ip():
    """Automatically determine broadcast address based on local IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        parts = local_ip.split(".")
        parts[-1] = "255"
        return ".".join(parts)
    except Exception:
        return "255.255.255.255"  # Fallback

def build_ping(user_id):
    return f"TYPE: PING\nUSER_ID: {user_id}\n\n"

def send_ping(user_id, interval=10, verbose=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    broadcast_ip = get_broadcast_ip()
    if verbose:
        print(f"[INFO] Using broadcast address: {broadcast_ip}")

    while True:
        msg = build_ping(user_id)
        try:
            sock.sendto(msg.encode("utf-8"), (broadcast_ip, PORT))
            if verbose:
                print(f"[PING] Sent ping to {broadcast_ip}")
        except Exception as e:
            print(f"❌ Failed to send ping: {e}")
        time.sleep(interval)
