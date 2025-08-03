# === listener.py ===
import socket
import time
from shared_state import dm_history, active_dm_user

PORT = 50999
BUFFER_SIZE = 65535
LISTEN_IP = ''

peer_table = {}      # user_id -> last_seen_time
profile_data = {}    # user_id -> {display_name, status}
user_ip_map = {}     # user_id -> actual IP address
post_feed = []       # list of posts (only those received via broadcast)

def start_listener(verbose=False):
    global dm_history, active_dm_user, user_ip_map

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LISTEN_IP, PORT))

    print(f"[INFO] Listening on UDP port {PORT}...")

    try:
        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
            except ConnectionResetError as e:
                print(f"⚠️  Connection reset: {e}")
                continue

            message = data.decode("utf-8", errors="ignore")

            if message.startswith("TYPE: PING"):
                user_id = None
                for line in message.strip().split("\n"):
                    if line.startswith("USER_ID:"):
                        user_id = line.split(":", 1)[1].strip()
                if user_id:
                    peer_table[user_id] = time.time()
                    user_ip_map[user_id] = addr[0]
                    if verbose:
                        print(f"< RECV PING from {addr[0]} - User: {user_id}")

            elif message.startswith("TYPE: PROFILE"):
                user_id, display_name, status = None, "Unknown", "No status"
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
                    user_ip_map[user_id] = addr[0]
                    if verbose:
                        print(f"< RECV PROFILE from {user_id}: {display_name}")

            elif message.startswith("TYPE: DM"):
                from_user, content, message_id = "Unknown", "", None
                for line in message.strip().split("\n"):
                    if line.startswith("FROM:"):
                        from_user = line.split(":", 1)[1].strip()
                    elif line.startswith("CONTENT:"):
                        content = line.split(":", 1)[1].strip()
                    elif line.startswith("MESSAGE_ID:"):
                        message_id = line.split(":", 1)[1].strip()

                sender_name = profile_data.get(from_user, {}).get("display_name", from_user.split("@")[0])
                user_ip_map[from_user] = addr[0]

                if from_user not in dm_history:
                    dm_history[from_user] = []
                dm_history[from_user].append(f"{sender_name}: {content}")

                if active_dm_user == from_user:
                    print(f"\n💬 {sender_name}: {content}")
                    print(f"[You → {sender_name}]: ", end="", flush=True)
                else:
                    print(f"\n💬 New message from {sender_name}: {content}")
                    print("> ", end="", flush=True)

                if message_id:
                    ack = f"TYPE: ACK\nMESSAGE_ID: {message_id}\nSTATUS: RECEIVED\n\n"
                    sock.sendto(ack.encode("utf-8"), addr)
                    if verbose:
                        print(f"✅ Sent ACK for message {message_id}")

            elif message.startswith("TYPE: ACK") and verbose:
                for line in message.strip().split("\n"):
                    if line.startswith("MESSAGE_ID:"):
                        print(f"✅ ACK received for message {line.split(':', 1)[1].strip()}")

            elif verbose:
                print(f"< RECV UNKNOWN from {addr[0]}:{addr[1]}\n{message}\n{'-'*40}")

    except KeyboardInterrupt:
        print("[INFO] Listener stopped.")
    finally:
        sock.close()
