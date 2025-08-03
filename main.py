import threading
import time
import socket
import random
import os
import uuid

from listener import start_listener, peer_table, profile_data
from ping import send_ping


following = set()

def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

def get_fake_ip():
    """Simulate a fake IP for local multi-user testing."""
    return f"192.168.1.{random.randint(100, 200)}"

def register_user():
    print("==== Welcome to LSNP ====\n")
    verbose_input = input("Enable Verbose Mode? (y/n): ").lower()
    verbose = verbose_input == "y"

    username = input("\nEnter your username: ").strip()
    display_name = input("Enter your display name: ").strip()
    status = input("Enter your status: ").strip()

    fake_ip = get_fake_ip()
    user_id = f"{username}@{fake_ip}"

    print("\n✅ Profile created!\n")

    return {
        "verbose": verbose,
        "username": username,
        "display_name": display_name,
        "status": status,
        "user_id": user_id,
        "ip": fake_ip
    }

def _send_unicast(message, user_id):
    ip = user_id.split("@")[1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message.encode("utf-8"), (ip, 50999))
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

def main():
    user = register_user()

    # Start the UDP listener thread
    listener_thread = threading.Thread(
        target=start_listener,
        kwargs={"verbose": user["verbose"]},
        daemon=True
    )
    listener_thread.start()

    # Start the periodic PING broadcaster thread
    ping_thread = threading.Thread(
        target=send_ping,
        kwargs={"user_id": user["user_id"], "interval": 10, "verbose": user["verbose"]},  # use 300 in prod
        daemon=True
    )
    ping_thread.start()

    # CLI interaction loop
    while True:
        show_menu()
        choice = input("Select an option: ").strip()

        if choice == "0":
            user["verbose"] = not user["verbose"]
            print(f"Verbose Mode {'enabled' if user['verbose'] else 'disabled'}.\n")


        elif choice == "1":
            while True:
                now = time.time()
                peers = [
                    uid for uid, last_seen in peer_table.items()
                    if now - last_seen < 30 and uid != user["user_id"]
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
                    follow_msg = (
                        f"TYPE: FOLLOW\n"
                        f"MESSAGE_ID: {message_id}\n"
                        f"FROM: {user['user_id']}\n"
                        f"TO: {target_uid}\n"
                        f"TIMESTAMP: {timestamp}\n"
                        f"TOKEN: {token}\n\n"
                    )
                    _send_unicast(follow_msg, target_uid)
                    following.add(target_uid)
                    print(f"✅ Followed {target_uid}\n")

                elif sub_choice.startswith("U"):
                    unfollow_msg = (
                        f"TYPE: UNFOLLOW\n"
                        f"MESSAGE_ID: {message_id}\n"
                        f"FROM: {user['user_id']}\n"
                        f"TO: {target_uid}\n"
                        f"TIMESTAMP: {timestamp}\n"
                        f"TOKEN: {token}\n\n"
                    )
                    _send_unicast(unfollow_msg, target_uid)
                    following.discard(target_uid)
                    print(f"🚫 Unfollowed {target_uid}\n")

        elif choice == "2":
            from listener import post_feed  # Get latest post data each time

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

                    post_msg = (
                        f"TYPE: POST\n"
                        f"USER_ID: {user['user_id']}\n"
                        f"CONTENT: {content}\n"
                        f"TTL: {ttl}\n"
                        f"MESSAGE_ID: {message_id}\n"
                        f"TOKEN: {token}\n\n"
                    )

                    # Send via broadcast
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.sendto(post_msg.encode("utf-8"), ("<broadcast>", 50999))
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









        elif choice == "7":
            print(f"\nUsername: {user['username']}")
            print(f"Display Name: {user['display_name']}")
            print(f"Status: {user['status']}")
            print(f"User ID: {user['user_id']}\n")

        elif choice == "8":
            print("\nExiting LSNP...\n")
            break

        else:
            print("That feature is not yet implemented.\n")

if __name__ == "__main__":
    main()
