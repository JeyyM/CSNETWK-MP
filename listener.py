# === Fixed listener.py ===
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
    global dm_history, active_dm_user, user_ip_map, peer_table, profile_data

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
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
                message = data.decode("utf-8", errors="ignore")
                
                if verbose:
                    print(f"\n[DEBUG] Received from {addr}: {message[:100]}...")

            except ConnectionResetError as e:
                if verbose:
                    print(f"⚠️  Connection reset: {e}")
                continue
            except Exception as e:
                if verbose:
                    print(f"⚠️  Receive error: {e}")
                continue

            # Parse message type
            if message.startswith("TYPE: PING"):
                handle_ping(message, addr, verbose)
            elif message.startswith("TYPE: PROFILE"):
                handle_profile(message, addr, verbose)
            elif message.startswith("TYPE: DM"):
                handle_dm(message, addr, verbose)
            elif message.startswith("TYPE: POST"):
                handle_post(message, addr, verbose)
            elif message.startswith("TYPE: ACK"):
                if verbose:
                    print(f"✅ ACK received from {addr}")
            elif verbose:
                print(f"< RECV UNKNOWN from {addr}\n{message}\n{'-'*40}")

    except KeyboardInterrupt:
        print("\n[INFO] Listener stopped.")
    finally:
        sock.close()

def handle_ping(message, addr, verbose):
    global peer_table, user_ip_map
    
    user_id = None
    for line in message.strip().split("\n"):
        if line.startswith("USER_ID:"):
            user_id = line.split(":", 1)[1].strip()
            break
    
    if user_id:
        peer_table[user_id] = time.time()
        user_ip_map[user_id] = addr[0]
        if verbose:
            print(f"< PING from {user_id} at {addr[0]}")

def handle_profile(message, addr, verbose):
    global peer_table, profile_data, user_ip_map
    
    user_id, display_name, status = None, "Unknown", "No status"
    for line in message.strip().split("\n"):
        line = line.strip()
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
            print(f"< PROFILE from {user_id} ({display_name}) at {addr[0]}")

def handle_dm(message, addr, verbose):
    global dm_history, active_dm_user, user_ip_map, profile_data
    
    from_user, to_user, content, message_id = None, None, "", None
    
    # More robust parsing
    lines = [line.strip() for line in message.strip().split("\n") if line.strip()]
    for line in lines:
        if line.startswith("FROM:"):
            from_user = line.split(":", 1)[1].strip()
        elif line.startswith("TO:"):
            to_user = line.split(":", 1)[1].strip()
        elif line.startswith("CONTENT:"):
            content = line.split(":", 1)[1].strip()
        elif line.startswith("MESSAGE_ID:"):
            message_id = line.split(":", 1)[1].strip()

    if verbose:
        print(f"[DEBUG] DM parsed - From: '{from_user}', To: '{to_user}', Content: '{content}'")

    if not from_user or not content:
        if verbose:
            print(f"[DEBUG] Invalid DM - missing from_user or content")
        return

    # Update sender's IP
    user_ip_map[from_user] = addr[0]
    
    # Get display name, fallback to username part before @
    sender_display = profile_data.get(from_user, {}).get("display_name")
    if not sender_display:
        # Extract username from user_id (before @)
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

    # Send ACK if requested
    if message_id:
        send_ack(message_id, addr, verbose)

def send_ack(message_id, addr, verbose):
    ack_msg = f"TYPE: ACK\nMESSAGE_ID: {message_id}\nSTATUS: RECEIVED\n\n"
    try:
        ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ack_sock.sendto(ack_msg.encode("utf-8"), addr)
        ack_sock.close()
        if verbose:
            print(f"✅ Sent ACK for {message_id} to {addr}")
    except Exception as e:
        if verbose:
            print(f"❌ Failed to send ACK: {e}")

def handle_post(message, addr, verbose):
    global post_feed, profile_data
    
    user_id, content, timestamp, ttl = None, "", int(time.time()), 3600
    for line in message.strip().split("\n"):
        line = line.strip()
        if line.startswith("USER_ID:"):
            user_id = line.split(":", 1)[1].strip()
        elif line.startswith("CONTENT:"):
            content = line.split(":", 1)[1].strip()
        elif line.startswith("TTL:"):
            try:
                ttl = int(line.split(":", 1)[1].strip())
            except ValueError:
                ttl = 3600

    if user_id and content:
        display_name = profile_data.get(user_id, {}).get("display_name", user_id.split("@")[0])
        post = {
            "user_id": user_id,
            "display_name": display_name,
            "content": content,
            "timestamp": timestamp,
            "ttl": ttl,
            "likes": set()
        }
        post_feed.append(post)
        if verbose:
            print(f"< POST from {user_id}: {content}")

# === Fixed main.py registration and DM sections ===

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
    """Send a unicast message to a specific user"""
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

# Updated DM section for main()
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
            msg = input(f"[You → {target_display}]: ").strip()
        except KeyboardInterrupt:
            break
        
        if msg == "/exit":
            print("👋 Exiting chat.\n")
            break
            
        elif msg == "/refresh":
            if target_uid in dm_history:
                print("\n📜 Chat History:")
                for message in dm_history[target_uid]:
                    print(f"  {message}")
            else:
                print("📭 No messages yet.")
            continue
            
        elif msg == "/debug":
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
            
        elif msg == "/test":
            msg = f"Test message at {time.strftime('%H:%M:%S')}"
            
        if not msg:
            continue

        # Create and send DM
        message_id = f"msg_{int(time.time())}_{random.randint(1000,9999)}"
        timestamp = int(time.time())
        
        dm_msg = (
            f"TYPE: DM\n"
            f"FROM: {user['user_id']}\n"
            f"TO: {target_uid}\n"
            f"CONTENT: {msg}\n"
            f"TIMESTAMP: {timestamp}\n"
            f"MESSAGE_ID: {message_id}\n\n"
        )

        if user["verbose"]:
            print(f"[DEBUG] Sending: {msg}")

        success = _send_unicast(dm_msg, target_uid, user["verbose"])
        if success:
            # Add to your own history
            if target_uid not in dm_history:
                dm_history[target_uid] = []
            dm_history[target_uid].append(f"{user['display_name']}: {msg}")
            
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