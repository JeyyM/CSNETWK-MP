import socket
import time

# Constants
PORT = 50999
BUFFER_SIZE = 65535
LISTEN_IP = ''

# Shared Data
peer_table = {}      # user_id -> last_seen_time
profile_data = {}    # user_id -> {display_name, status}
post_feed = []       # list of posts (only those received via broadcast)

def start_listener(verbose=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LISTEN_IP, PORT))

    print(f"[INFO] Listening on UDP port {PORT}...")

    try:
        while True:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            message = data.decode("utf-8", errors="ignore")

            if message.startswith("TYPE: PING"):
                lines = message.strip().split("\n")
                for line in lines:
                    if line.startswith("USER_ID:"):
                        user_id = line.split(":", 1)[1].strip()
                        peer_table[user_id] = time.time()

                if verbose:
                    print(f"< RECV PING from {addr[0]}")

            elif message.startswith("TYPE: PROFILE"):
                user_id = None
                display_name = "Unknown"
                status = "No status"

                for line in message.strip().split("\n"):
                    if line.startswith("USER_ID:"):
                        user_id = line.split(":", 1)[1].strip()
                    elif line.startswith("DISPLAY_NAME:"):
                        display_name = line.split(":", 1)[1].strip()
                    elif line.startswith("STATUS:"):
                        status = line.split(":", 1)[1].strip()

                if user_id:
                    profile_data[user_id] = {
                        "display_name": display_name,
                        "status": status
                    }
                    peer_table[user_id] = time.time()

            elif message.startswith("TYPE: POST"):
                user_id = None
                content = ""
                ttl = 3600
                message_id = None
                timestamp = int(time.time())

                for line in message.strip().split("\n"):
                    if line.startswith("USER_ID:"):
                        user_id = line.split(":", 1)[1].strip()
                    elif line.startswith("CONTENT:"):
                        content = line.split(":", 1)[1].strip()
                    elif line.startswith("TTL:"):
                        ttl = int(line.split(":", 1)[1].strip())
                    elif line.startswith("MESSAGE_ID:"):
                        message_id = line.split(":", 1)[1].strip()

                if user_id and content:
                    display_name = profile_data.get(user_id, {}).get("display_name", user_id.split("@")[0])
                    post_feed.append({
                        "user_id": user_id,
                        "display_name": display_name,
                        "content": content,
                        "timestamp": timestamp,
                        "message_id": message_id,
                        "likes": set()
                    })

                    if verbose:
                        print(f"📣 New POST from {user_id}")

            elif verbose:
                print(f"< RECV from {addr[0]}:{addr[1]}\n{message}\n{'-'*40}")

    except KeyboardInterrupt:
        print("[INFO] Listener stopped.")
    finally:
        sock.close()
