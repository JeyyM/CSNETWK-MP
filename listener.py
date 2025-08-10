# === listener.py (RFC-safe parsing & terminator enforcement) ===
import socket
import time
import random

from shared_state import dm_history, active_dm_user

# NEW: use the protocol helpers so we parse/build consistently
from protocol import parse_message, build_message

PORT = 50999
BUFFER_SIZE = 65535
LISTEN_IP = ''

peer_table = {}      # user_id -> last_seen_time
profile_data = {}    # user_id -> {display_name, status}
user_ip_map = {}     # user_id -> actual IP address
post_feed = []       # list of posts (only those received via broadcast)

def start_listener(verbose=False):
    global dm_history, active_dm_user, user_ip_map, peer_table, profile_data

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # receive broadcasts

    # Try to bind to the port, with retry logic
    max_retries = 5
    for retry in range(max_retries):
        try:
            sock.bind((LISTEN_IP, PORT))
            break
        except OSError as e:
            if retry == max_retries - 1:
                print(f"❌ Failed to bind to port {PORT} after {max_retries} attempts: {e}")
                return
            print(f"⚠️  Retry {retry + 1}: Failed to bind to port {PORT}, retrying in 1 second...")
            time.sleep(1)

    print(f"[INFO] Listening on UDP port {PORT}...")

    try:
        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                raw = data.decode("utf-8", errors="ignore")
            except ConnectionResetError as e:
                if verbose:
                    print(f"⚠️  Connection reset: {e}")
                continue
            except Exception as e:
                if verbose:
                    print(f"⚠️  Receive error: {e}")
                continue

            # RFC-safe parse: enforce \n\n and get a dict of fields
            msg = parse_message(raw)
            if not msg:
                if verbose:
                    print(f"DROP! Invalid or unterminated message from {addr}.")
                continue

            if verbose:
                t = time.strftime("%H:%M:%S")
                print(f"\nRECV< {t} {addr[0]}:{addr[1]} TYPE={msg.get('TYPE','?')}")

            # Route by TYPE (no assumption about field order)
            mtype = msg.get("TYPE", "")
            if mtype == "PING":
                handle_ping(msg, addr, verbose)
            elif mtype == "PROFILE":
                handle_profile(msg, addr, verbose)
            elif mtype == "DM":
                handle_dm(msg, addr, verbose)
            elif mtype == "POST":
                handle_post(msg, addr, verbose)
            elif mtype == "LIKE":
                handle_like(msg, addr, verbose)

            elif mtype == "ACK":
                if verbose:
                    print(f"✅ ACK received from {addr}")
            else:
                if verbose:
                    print(f"< RECV UNKNOWN from {addr}\n{raw}\n{'-'*40}")

    except KeyboardInterrupt:
        print("\n[INFO] Listener stopped.")
    finally:
        sock.close()

def handle_ping(msg, addr, verbose):
    """Process TYPE: PING"""
    global peer_table, user_ip_map
    user_id = msg.get("USER_ID")
    if not user_id:
        if verbose: print("[DEBUG] PING missing USER_ID")
        return

    peer_table[user_id] = time.time()
    user_ip_map[user_id] = addr[0]
    if verbose:
        print(f"📡 PING from {user_id} at {addr[0]}")

def handle_profile(msg, addr, verbose):
    """Process TYPE: PROFILE"""
    global peer_table, profile_data, user_ip_map
    user_id = msg.get("USER_ID")
    if not user_id:
        if verbose: print("[DEBUG] PROFILE missing USER_ID")
        return

    display_name = msg.get("DISPLAY_NAME", "Unknown")
    status = msg.get("STATUS", "No status")

    profile_data[user_id] = {
        "display_name": display_name,
        "status": status
    }
    peer_table[user_id] = time.time()
    user_ip_map[user_id] = addr[0]
    if verbose:
        print(f"👤 PROFILE from {user_id} ({display_name}) at {addr[0]}")

def handle_dm(msg, addr, verbose):
    """Process TYPE: DM"""
    global dm_history, active_dm_user, user_ip_map, profile_data

    from_user = msg.get("FROM")
    to_user = msg.get("TO")
    content = msg.get("CONTENT", "")
    message_id = msg.get("MESSAGE_ID")

    if verbose:
        print(f"[DEBUG] DM parsed - From: '{from_user}', To: '{to_user}', Content: '{content}'")

    if not from_user or not content:
        if verbose:
            print(f"[DEBUG] Invalid DM - missing FROM or CONTENT")
        return

    # Update sender's IP
    user_ip_map[from_user] = addr[0]

    # Get display name, fallback to username part before @
    sender_display = profile_data.get(from_user, {}).get("display_name")
    if not sender_display:
        sender_display = from_user.split("@")[0] if "@" in from_user else from_user

    # Initialize conversation history
    if from_user not in dm_history:
        dm_history[from_user] = []

    # Add message to history
    message_entry = f"{sender_display}: {content}"
    dm_history[from_user].append(message_entry)

    if verbose:
        print(f"[DEBUG] Added to history: {message_entry}")
        print(f"[DEBUG] Active DM user: {active_dm_user}, From user: {from_user}")

    # Display message appropriately
    if active_dm_user == from_user:
        print(f"\n💬 {sender_display}: {content}")
        print(f"[You → {sender_display}]: ", end="", flush=True)
    else:
        print(f"\n💬 New message from {sender_display}: {content}")
        print("> ", end="", flush=True)

    # Send ACK if the message has a MESSAGE_ID
    if message_id:
        send_ack(message_id, addr, verbose)

def send_ack(message_id, addr, verbose):
    """Send TYPE: ACK using build_message()"""
    ack_fields = {
        "TYPE": "ACK",
        "MESSAGE_ID": message_id,
        "STATUS": "RECEIVED",
    }
    ack_msg = build_message(ack_fields)
    try:
        ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ack_sock.sendto(ack_msg.encode("utf-8"), addr)
        ack_sock.close()
        if verbose:
            print(f"✅ Sent ACK for {message_id} to {addr}")
    except Exception as e:
        if verbose:
            print(f"❌ Failed to send ACK: {e}")

def handle_post(msg, addr, verbose):
    global post_feed, profile_data

    user_id = msg.get("USER_ID")
    content = msg.get("CONTENT", "")
    ttl_raw = msg.get("TTL")
    ts_raw = msg.get("TIMESTAMP")  # <-- read sender's timestamp

    if not user_id or not content:
        if verbose:
            print("[DEBUG] POST missing USER_ID or CONTENT")
        return

    try:
        timestamp = int(ts_raw) if ts_raw is not None else int(time.time())
    except ValueError:
        timestamp = int(time.time())

    try:
        ttl = int(ttl_raw) if ttl_raw is not None else 3600
    except ValueError:
        ttl = 3600

    display_name = profile_data.get(user_id, {}).get("display_name", user_id.split("@")[0])
    post = {
        "user_id": user_id,
        "display_name": display_name,
        "content": content,
        "timestamp": timestamp,   # <-- store sender's timestamp
        "ttl": ttl,
        "likes": set()
    }
    post_feed.append(post)
    if verbose:
        print(f"< POST from {user_id}: {content}")

def handle_like(msg, addr, verbose):
    """
    Process TYPE: LIKE
    We update the local post object that matches (author == TO) and (timestamp == POST_TIMESTAMP).
    Only the author is guaranteed to receive this (per RFC example), but if others do, it's harmless.
    """
    global post_feed, profile_data

    liker_uid = msg.get("FROM")
    author_uid = msg.get("TO")
    post_ts_raw = msg.get("POST_TIMESTAMP")
    action = msg.get("ACTION", "").upper()

    # Basic validation
    if not liker_uid or not author_uid or post_ts_raw is None or action not in {"LIKE", "UNLIKE"}:
        if verbose:
            print("[DEBUG] LIKE missing required fields")
        return

    try:
        post_ts = int(post_ts_raw)
    except ValueError:
        if verbose:
            print("[DEBUG] LIKE invalid POST_TIMESTAMP")
        return

    # Find the post locally
    target = None
    for p in post_feed:
        if p.get("user_id") == author_uid and int(p.get("timestamp", -1)) == post_ts:
            target = p
            break

    if not target:
        if verbose:
            print("[DEBUG] LIKE referenced post not found locally")
        return

    # Update the likes set
    if action == "LIKE":
        target["likes"].add(liker_uid)
    else:
        target["likes"].discard(liker_uid)

    # Friendly output (non-verbose printing per RFC suggests a short line)
    liker_name = profile_data.get(liker_uid, {}).get("display_name", liker_uid.split("@")[0])
    author_name = profile_data.get(author_uid, {}).get("display_name", author_uid.split("@")[0])
    if verbose or author_uid in (profile_data.keys()):  # print for author or when verbose
        verb = "likes" if action == "LIKE" else "unliked"
        print(f"💌 {liker_name} {verb} your post (ts={post_ts}).")

# === (These helpers were in your snippet; keeping them here unchanged) ===
def register_user():
    print("==== Welcome to LSNP ====")
    verbose_input = input("Enable Verbose Mode? (y/n): ").lower()
    verbose = verbose_input == "y"

    username = input("Enter your username: ").strip()
    display_name = input("Enter your display name: ").strip()
    status = input("Enter your status: ").strip()

    # Get the actual local IP instead of hardcoding 127.0.0.1
    try:
        # Connect to a remote address to determine local IP
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_sock.connect(("8.8.8.8", 80))
        local_ip = temp_sock.getsockname()[0]
        temp_sock.close()
    except Exception:
        local_ip = "127.0.0.1"

    # Create unique user ID with timestamp to avoid conflicts
    timestamp_suffix = str(int(time.time()))[-4:]  # Last 4 digits of timestamp
    user_id = f"{username}_{timestamp_suffix}@{local_ip}"

    print(f"\n✅ Profile created! Your User ID: {user_id}\n")
    return {
        "verbose": verbose,
        "username": username,
        "display_name": display_name,
        "status": status,
        "user_id": user_id,
        "ip": local_ip
    }

def _send_unicast(message, user_id, verbose=False):
    """Send a unicast message to a specific user (expects a string already built)."""
    if user_id not in user_ip_map:
        if verbose:
            print(f"[DEBUG] No IP mapping for {user_id}")
        return False

    ip = user_ip_map[user_id]

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)  # 5 second timeout
        sock.sendto(message.encode("utf-8"), (ip, 50999))
        sock.close()

        if verbose:
            print(f"[DEBUG] Sent to {user_id} at {ip}")
        return True

    except socket.timeout:
        print(f"❌ Timeout sending to {user_id} ({ip})")
        return False
    except Exception as e:
        print(f"❌ Failed to send to {user_id} ({ip}): {e}")
        return False

# Updated DM section for main-like flow; uses build_message() now
def handle_dm_chat(user, peers):
    """Handle the DM chat functionality"""
    global active_dm_user

    print("\n==== Active Peers for DM ====")
    for idx, uid in enumerate(peers, 1):
        display = profile_data.get(uid, {}).get("display_name", uid.split("@")[0])
        message_count = len(dm_history.get(uid, []))
        message_indicator = f" ({message_count} messages)" if message_count > 0 else ""
        ip = user_ip_map.get(uid, "Unknown IP")
        print(f"[{idx}] {display} ({uid}) - IP: {ip}{message_indicator}")
    print("=============================\n")

    selected = input("Select peer number to DM: ").strip()
    try:
        target_uid = peers[int(selected) - 1]
    except (IndexError, ValueError):
        print("❌ Invalid selection.\n")
        return

    target_display = profile_data.get(target_uid, {}).get("display_name", target_uid.split("@")[0])
    target_ip = user_ip_map.get(target_uid, "Unknown")

    print(f"\n💬 Chat with {target_display} ({target_ip})")
    print("Commands: /exit (leave), /refresh (reload), /debug (info), /test (send test)")
    print("-" * 50)

    # Set active DM user
    active_dm_user = target_uid

    # Show existing history
    if target_uid in dm_history and dm_history[target_uid]:
        print("📜 Recent Messages:")
        recent_messages = dm_history[target_uid][-10:]  # Show last 10
        for msg in recent_messages:
            print(f"  {msg}")
        print("-" * 50)

    while True:
        try:
            msg_text = input(f"[You → {target_display}]: ").strip()
        except KeyboardInterrupt:
            break

        if msg_text == "/exit":
            print("👋 Exiting chat.\n")
            break

        elif msg_text == "/refresh":
            if target_uid in dm_history:
                print("\n📜 Chat History:")
                for message in dm_history[target_uid]:
                    print(f"  {message}")
            else:
                print("📭 No messages yet.")
            continue

        elif msg_text == "/debug":
            print(f"\n=== DEBUG INFO ===")
            print(f"Your ID: {user['user_id']}")
            print(f"Target ID: {target_uid}")
            print(f"Target IP: {user_ip_map.get(target_uid, 'Not found')}")
            print(f"Active DM: {active_dm_user}")
            print(f"Known peers: {list(peer_table.keys())}")
            print(f"IP mappings: {user_ip_map}")
            if target_uid in dm_history:
                print(f"Message count: {len(dm_history[target_uid])}")
            print("==================\n")
            continue

        elif msg_text == "/test":
            msg_text = f"Test message at {time.strftime('%H:%M:%S')}"

        if not msg_text:
            continue

        # Create and send DM using build_message()
        message_id = f"msg_{int(time.time())}_{random.randint(1000,9999)}"
        timestamp = int(time.time())

        dm_fields = {
            "TYPE": "DM",
            "FROM": user["user_id"],
            "TO": target_uid,
            "CONTENT": msg_text,
            "TIMESTAMP": timestamp,
            "MESSAGE_ID": message_id,
        }
        dm_msg = build_message(dm_fields)

        if user["verbose"]:
            print(f"[DEBUG] Sending: {msg_text}")

        success = _send_unicast(dm_msg, target_uid, user["verbose"])
        if success:
            # Add to your own history
            if target_uid not in dm_history:
                dm_history[target_uid] = []
            dm_history[target_uid].append(f"{user['display_name']}: {msg_text}")

            # Show recent messages
            recent = dm_history[target_uid][-3:]
            print("─" * 30)
            for recent_msg in recent:
                print(f"  {recent_msg}")
            print("─" * 30)
        else:
            print(f"❌ Failed to send message")
            if target_uid not in user_ip_map:
                print("   → No IP address known for target user")
            else:
                print(f"   → Target IP: {user_ip_map[target_uid]}")

    active_dm_user = None
