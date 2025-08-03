# === listener.py ===
import socket
import time
from shared_state import dm_history, active_dm_user

PORT = 50999
BUFFER_SIZE = 65535
LISTEN_IP = ''

peer_table = {}      # user_id -> last_seen_time
profile_data = {}    # user_id -> {display_name, status}
post_feed = []       # list of posts (only those received via broadcast)

def start_listener(verbose=False):
    global dm_history, active_dm_user
    
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
                    print(f"< RECV PING from {addr[0]} - User: {user_id}")

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
                    
                    if verbose:
                        print(f"< RECV PROFILE from {user_id}: {display_name}")

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

            elif message.startswith("TYPE: DM"):
                from_user = "Unknown"
                content = ""
                message_id = None

                for line in message.strip().split("\n"):
                    if line.startswith("FROM:"):
                        from_user = line.split(":", 1)[1].strip()
                    elif line.startswith("CONTENT:"):
                        content = line.split(":", 1)[1].strip()
                    elif line.startswith("MESSAGE_ID:"):
                        message_id = line.split(":", 1)[1].strip()

                # Get sender's display name
                sender_name = profile_data.get(from_user, {}).get("display_name", from_user.split("@")[0])
                
                # Debug info
                if verbose:
                    print(f"📨 DM received from {from_user} ({sender_name}): '{content}'")
                    print(f"    Profile data exists for sender: {from_user in profile_data}")
                    print(f"    Current active DM user: {active_dm_user}")
                
                # Add to DM history - ALWAYS store incoming messages
                if from_user not in dm_history:
                    dm_history[from_user] = []
                
                # Store the incoming message
                dm_history[from_user].append(f"{sender_name}: {content}")
                
                if verbose:
                    print(f"    Stored message. Total messages from {from_user}: {len(dm_history[from_user])}")
                    print(f"    DM history keys: {list(dm_history.keys())}")
                
                # Show notification based on whether user is in active DM with this person
                if active_dm_user == from_user:
                    # User is actively chatting with this person - show message inline
                    print(f"\n💬 {sender_name}: {content}")
                    target_display = profile_data.get(from_user, {}).get("display_name", from_user.split('@')[0])
                    print(f"[You → {target_display}]: ", end="", flush=True)
                else:
                    # User is not in active chat - show notification
                    print(f"\n💬 New message from {sender_name}: {content}")
                    print("> ", end="", flush=True)

                # Send ACK if message has ID
                if message_id:
                    ack = f"TYPE: ACK\nMESSAGE_ID: {message_id}\nSTATUS: RECEIVED\n\n"
                    sock.sendto(ack.encode("utf-8"), addr)
                    if verbose:
                        print(f"    Sent ACK for message {message_id}")

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