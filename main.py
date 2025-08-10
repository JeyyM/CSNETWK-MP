import threading
import time
import socket
import os
import uuid

from protocol import build_message  # ✅ ensure consistent RFC formatting (\n\n)
from shared_state import dm_history, active_dm_user
from listener import start_listener, peer_table, profile_data, user_ip_map
from ping import send_ping, get_broadcast_ip

following = set()

def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

def broadcast_profile(user):
    """Broadcast TYPE: PROFILE using build_message()."""
    fields = {
        "TYPE": "PROFILE",
        "USER_ID": user["user_id"],
        "DISPLAY_NAME": user["display_name"],
        "STATUS": user["status"],
    }
    profile_msg = build_message(fields)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    broadcast_ip = get_broadcast_ip()
    sock.sendto(profile_msg.encode("utf-8"), (broadcast_ip, 50999))
    sock.close()

def register_user():
    print("==== Welcome to LSNP ====")
    verbose_input = input("Enable Verbose Mode? (y/n): ").lower()
    verbose = verbose_input == "y"

    username = input("Enter your username: ").strip()
    display_name = input("Enter your display name: ").strip()
    status = input("Enter your status: ").strip()

    # ✅ Get real LAN IP (not 127.0.0.1)
    try:
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_sock.connect(("8.8.8.8", 80))
        ip = temp_sock.getsockname()[0]
        temp_sock.close()
    except Exception:
        ip = "127.0.0.1"  # fallback

    user_id = f"{username}@{ip}"

    print(f"\n✅ Profile created! Your User ID: {user_id}\n")
    return {
        "verbose": verbose,
        "username": username,
        "display_name": display_name,
        "status": status,
        "user_id": user_id,
        "ip": ip
    }

def _send_unicast(message, user_id, verbose=False):
    """Send a unicast message to a specific user."""
    ip = user_ip_map.get(user_id, "127.0.0.1")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(message.encode("utf-8"), (ip, 50999))
        if verbose:
            print(f"[DEBUG] Sent message to {user_id} at {ip}")
        return True
    except Exception as e:
        print(f"❌ Failed to send to {user_id} ({ip}): {e}")
        return False
    finally:
        sock.close()

def show_menu():
    print("==== LSNP CLI Menu ====\n")
    print("[0] Toggle Verbose Mode")
    print("[1] View Peer Profiles")
    print("[2] Posts Feed")
    print("[3] Send a Direct Message")
    print("[4] Send a Group Message")
    print("[5] Send a File")
    print("[6] Play Tic Tac Toe")
    print("[7] My Profile")
    print("[8] Exit\n")

def display_dm_history(target_uid, user_display_name):
    """Display the full DM history for a conversation."""
    history = dm_history.get(target_uid, [])
    if history:
        print("📜 Chat History:")
        for line in history:
            print(line)
        print()
    else:
        print("📭 No chat history with this user yet.\n")

def show_recent_messages(target_uid, count=20):  # bump to 20 (or None to show all)
    history = dm_history.get(target_uid, [])
    if history:
        recent = history[-count:] if count else history  # show all if count is None/Falsey
        print("\n" + "─" * 40)
        for msg in recent:
            print(msg)
        print("─" * 40)

def add_to_dm_history(user_id, message, is_outgoing=False, user_display_name="You"):
    """Add a message to DM history."""
    global dm_history
    if user_id not in dm_history:
        dm_history[user_id] = []
    if is_outgoing:
        dm_history[user_id].append(f"{user_display_name}: {message}")

def main():
    global active_dm_user
    user = register_user()

    # Start the UDP listener thread
    listener_thread = threading.Thread(
        target=start_listener,
        kwargs={"verbose": user["verbose"]},
        daemon=True
    )
    listener_thread.start()

    # Broadcast profile immediately
    time.sleep(1)  # Give listener time to start
    broadcast_profile(user)

    # Start the periodic PING broadcaster thread (keep short interval during dev)
    ping_thread = threading.Thread(
        target=send_ping,
        kwargs={"user_id": user["user_id"], "interval": 10, "verbose": user["verbose"]},
        daemon=True
    )
    ping_thread.start()

    # Periodic PROFILE broadcaster thread (keep short interval during dev)
    def periodic_profile_broadcast():
        while True:
            time.sleep(30)
            broadcast_profile(user)

    profile_thread = threading.Thread(target=periodic_profile_broadcast, daemon=True)
    profile_thread.start()

    # CLI interaction loop
    while True:
        show_menu()
        choice = input("Select an option: ").strip()

        if choice == "0":
            user["verbose"] = not user["verbose"]
            print(f"Verbose Mode {'enabled' if user['verbose'] else 'disabled'}.\n")

        elif choice == "1":
            # View Peer Profiles + Follow/Unfollow
            while True:
                now = time.time()
                peers = [
                    uid for uid, last_seen in peer_table.items()
                    if now - last_seen < 60 and uid != user["user_id"]
                ]

                if not peers:
                    print("\nNo active peers found.\n")
                    break

                print("\n==== Active Peers ====")
                key_map = {}
                for idx, uid in enumerate(peers, start=1):
                    display = profile_data.get(uid, {}).get("display_name", uid.split("@")[0])
                    status = profile_data.get(uid, {}).get("status", "No status")

                    following_status = f"You follow {display}" if uid in following else f"You are not following {display}"
                    action_key = f"U{idx}" if uid in following else f"F{idx}"
                    key_map[action_key] = uid

                    print(f"{idx}. {display} ({uid})")
                    print(f"   ➤ {following_status}")
                    print(f"   🗨️  Status    : {status}")
                    print(f"   ⏱️  Last Seen : {int(now - peer_table[uid])} seconds ago")
                    print(f"   🎛️  Press [{action_key}] to {'Unfollow' if uid in following else 'Follow'}\n")

                print("======================")
                print(f"Total Peers: {len(peers)}")
                sub_choice = input("\nChoose an option: [F#] to follow, [U#] to unfollow, [B] to go back\n").strip().upper()

                if sub_choice == "B":
                    break

                target_uid = key_map.get(sub_choice)
                if not target_uid:
                    print("❌ Invalid option.\n")
                    continue

                message_id = uuid.uuid4().hex[:8]
                timestamp = int(time.time())
                ttl = 3600
                token = f"{user['user_id']}|{timestamp+ttl}|follow"

                if sub_choice.startswith("F"):
                    # TYPE: FOLLOW
                    fields = {
                        "TYPE": "FOLLOW",
                        "MESSAGE_ID": message_id,
                        "FROM": user["user_id"],
                        "TO": target_uid,
                        "TIMESTAMP": timestamp,
                        "TOKEN": token,
                    }
                    follow_msg = build_message(fields)
                    _send_unicast(follow_msg, target_uid, user["verbose"])
                    following.add(target_uid)
                    print(f"✅ Followed {target_uid}\n")

                elif sub_choice.startswith("U"):
                    # TYPE: UNFOLLOW
                    fields = {
                        "TYPE": "UNFOLLOW",
                        "MESSAGE_ID": message_id,
                        "FROM": user["user_id"],
                        "TO": target_uid,
                        "TIMESTAMP": timestamp,
                        "TOKEN": token,
                    }
                    unfollow_msg = build_message(fields)
                    _send_unicast(unfollow_msg, target_uid, user["verbose"])
                    following.discard(target_uid)
                    print(f"🚫 Unfollowed {target_uid}\n")

        elif choice == "2":
            # Posts Feed
            from listener import post_feed

            while True:
                sub_choice = input("\n[A] Add New Post\n[V] View Posts\n[B] Back to Main Menu\nSelect: ").strip().upper()

                if sub_choice == "A":
                    content = input("Enter your post (blank to cancel): ").strip()
                    if not content:
                        print("❌ Post canceled.\n")
                        continue

                    message_id = uuid.uuid4().hex[:8]
                    timestamp = int(time.time())
                    ttl = 3600
                    token = f"{user['user_id']}|{timestamp+ttl}|broadcast"

                    # TYPE: POST (broadcast)
                    fields = {
                        "TYPE": "POST",
                        "USER_ID": user["user_id"],
                        "CONTENT": content,
                        "TTL": ttl,
                        "MESSAGE_ID": message_id,
                        "TOKEN": token,
                    }
                    post_msg = build_message(fields)

                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    broadcast_ip = get_broadcast_ip()
                    sock.sendto(post_msg.encode("utf-8"), (broadcast_ip, 50999))
                    sock.close()

                    print("✅ Post broadcasted. Your message is now visible to followers.\n")

                elif sub_choice == "V":
                    while True:
                        now = int(time.time())
                        visible_posts = [
                            post for post in post_feed
                            if post["user_id"] in following or post["user_id"] == user["user_id"]
                        ]

                        if not visible_posts:
                            print("\n📭 No posts to show from followed peers or yourself.\n")
                            break

                        print("\n==== LSNP Post Feed ====\n")
                        post_keys = {}
                        for idx, post in enumerate(visible_posts, start=1):
                            age = now - post["timestamp"]
                            liked = user["user_id"] in post["likes"]
                            print(f"[{idx}] ({age}s ago) {post['display_name']} ({post['user_id']})")
                            print(f"📝 {post['content']}")
                            print(f"❤️ Likes: {len(post['likes'])} – Press [{'U' if liked else 'L'}{idx}] to {'unlike' if liked else 'like'}\n")
                            post_keys[f"{'U' if liked else 'L'}{idx}"] = post

                        print("========================")
                        sub = input("\n[L#/U#] Like/Unlike post | [B] Back to Posts Menu\n").strip().upper()

                        if sub == "B":
                            break

                        post = post_keys.get(sub)
                        if not post:
                            print("❌ Invalid post number.")
                            continue

                        if sub.startswith("L"):
                            post["likes"].add(user["user_id"])
                            print("❤️ You liked the post.\n")

                        elif sub.startswith("U"):
                            post["likes"].discard(user["user_id"])
                            print("💔 You unliked the post.\n")

                elif sub_choice == "B":
                    break

                else:
                    print("❌ Invalid option.\n")

        elif choice == "3":
            # Send a Direct Message (unicast)
            now = time.time()
            peers = [uid for uid, last_seen in peer_table.items() if now - last_seen < 60 and uid != user["user_id"]]

            if not peers:
                print("No peers available for DM.\n")
                continue

            print("\n==== Active Peers for DM ====")
            for idx, uid in enumerate(peers, 1):
                display = profile_data.get(uid, {}).get("display_name", uid.split("@")[0])
                message_count = len(dm_history.get(uid, []))
                message_indicator = f" ({message_count} messages)" if message_count > 0 else ""
                print(f"[{idx}] {display} ({uid}){message_indicator}")
            print("=============================\n")

            selected = input("Select peer number to DM: ").strip()
            try:
                target_uid = peers[int(selected) - 1]
            except (IndexError, ValueError):
                print("❌ Invalid selection.\n")
                continue

            target_display = profile_data.get(target_uid, {}).get("display_name", target_uid.split("@")[0])
            print(f"\n💬 Entering DM chat with {target_display}. Type `/exit` to leave, `/refresh` to see new messages.\n")

            # Set active DM user for the listener to know
            active_dm_user = target_uid

            # Display existing chat history
            display_dm_history(target_uid, user["display_name"])

            while True:
                msg_text = input(f"[You → {target_display}]: ").strip()

                if msg_text == "/exit":
                    print("👋 Exiting DM chat.\n")
                    active_dm_user = None
                    break

                if msg_text == "/refresh":
                    print("\n🔄 Refreshing chat...\n")
                    display_dm_history(target_uid, user["display_name"])
                    continue

                if msg_text == "/debug":
                    print(f"\nDEBUG INFO:")
                    print(f"Target UID: {target_uid}")
                    print(f"Your UID: {user['user_id']}")
                    print(f"Target IP: {user_ip_map.get(target_uid, 'Not found')}")
                    print(f"DM History keys: {list(dm_history.keys())}")
                    print(f"Profile data keys: {list(profile_data.keys())}")
                    print(f"Active DM user: {active_dm_user}")
                    if target_uid in dm_history:
                        print(f"Messages with {target_uid}: {len(dm_history[target_uid])}")
                        for i, msg_line in enumerate(dm_history[target_uid]):
                            print(f"  {i+1}: {msg_line}")
                    else:
                        print(f"No message history with {target_uid}")
                    print()
                    continue

                if not msg_text:
                    continue

                message_id = uuid.uuid4().hex[:8]
                timestamp = int(time.time())
                token = f"{user['user_id']}|{timestamp+300}|chat"

                # TYPE: DM (unicast)
                fields = {
                    "TYPE": "DM",
                    "FROM": user["user_id"],
                    "TO": target_uid,
                    "CONTENT": msg_text,
                    "TIMESTAMP": timestamp,
                    "MESSAGE_ID": message_id,
                    "TOKEN": token,
                }
                dm_msg = build_message(fields)

                if user["verbose"]:
                    print(f"[DEBUG] Sending DM to {target_uid}: {msg_text}")

                success = _send_unicast(dm_msg, target_uid, user["verbose"])
                if success:
                    # Add your own message to history
                    add_to_dm_history(target_uid, msg_text, is_outgoing=True, user_display_name=user["display_name"])

                    # Show the recent conversation including your sent message
                    show_recent_messages(target_uid, count=5)

                else:
                    print(f"❌ Failed to send message to {target_display}")
                    if target_uid not in user_ip_map:
                        print("   No IP address known for target. Wait for their ping/profile.")
                    else:
                        print(f"   Target IP: {user_ip_map[target_uid]}")

        elif choice == "7":
            print(f"\nUsername: {user['username']}")
            print(f"Display Name: {user['display_name']}")
            print(f"Status: {user['status']}")
            print(f"User ID: {user['user_id']}")
            print(f"Profile data stored: {len(profile_data)} peers")
            print(f"DM conversations: {len(dm_history)}")
            for uid, msgs in dm_history.items():
                display = profile_data.get(uid, {}).get("display_name", uid.split("@")[0])
                print(f"  - {display} ({uid}): {len(msgs)} messages")
            print()

        elif choice == "8":
            print("\nExiting LSNP...\n")
            break

        else:
            print("That feature is not yet implemented.\n")

if __name__ == "__main__":
    main()
