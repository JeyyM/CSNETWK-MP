import threading
import time
import socket
import os
import uuid
import re

from protocol import build_message  # ✅ ensure consistent RFC formatting (\n\n)
from shared_state import dm_history, active_dm_user
from listener import start_listener, peer_table, profile_data, user_ip_map
from ping import send_ping, get_broadcast_ip
from game_client import start_game_invite, send_move, get_board

from state import ttt_invites, ttt_games
from game_client import start_game_invite, send_move


following = set()

def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

def _broadcast_to_all(sock, data_bytes):
    # Try subnet-directed and limited broadcast
    b1 = get_broadcast_ip()
    b2 = "255.255.255.255"
    for bcast in {b1, b2}:
        try:
            sock.sendto(data_bytes, (bcast, 50999))
        except Exception as e:
            print(f"⚠️ Broadcast to {bcast} failed: {e}")

def broadcast_profile(user):
    fields = {
        "TYPE": "PROFILE",
        "USER_ID": user["user_id"],
        "DISPLAY_NAME": user["display_name"],
        "STATUS": user["status"],
    }
    profile_msg = build_message(fields).encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    _broadcast_to_all(sock, profile_msg)   # <-- send to both
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

# --- in main.py ---

import re

def _ip_from_uid(uid: str) -> str | None:
    # Extract IPv4 after '@' if present, quick sanity check
    if "@" not in uid:
        return None
    ip = uid.split("@", 1)[1].strip()
    return ip if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) else None

def _send_unicast(message, user_id, verbose=False):
    """Send a unicast message to a specific user, with IP fallback from user_id."""
    ip = user_ip_map.get(user_id)
    if not ip:
        ip = _ip_from_uid(user_id)  # <-- fallback when we haven't seen their PROFILE/PING
        if verbose and ip:
            print(f"[DEBUG] Using IP parsed from UID ({user_id}) -> {ip}")
    if not ip:
        if verbose:
            print(f"[DEBUG] No IP mapping and no @IP in UID for {user_id}")
        return False

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
                sub_choice = input(
                    "\n[A] Add New Post\n[V] View Posts (Followed)\n[O] View ALL Posts (debug)\n[B] Back to Main Menu\nSelect: "
                ).strip().upper()

                if sub_choice == "A":
                    content = input("Enter your post (blank to cancel): ").strip()
                    if not content:
                        print("❌ Post canceled.\n")
                        continue

                    message_id = uuid.uuid4().hex[:8]
                    timestamp = int(time.time())
                    ttl = 3600
                    token = f"{user['user_id']}|{timestamp+ttl}|broadcast"

                    # TYPE: POST (broadcast) — includes TIMESTAMP for LIKE references
                    fields = {
                        "TYPE": "POST",
                        "USER_ID": user["user_id"],
                        "CONTENT": content,
                        "TIMESTAMP": timestamp,
                        "TTL": ttl,
                        "MESSAGE_ID": message_id,
                        "TOKEN": token,
                    }
                    post_msg = build_message(fields)

                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    _broadcast_to_all(sock, post_msg.encode("utf-8"))  # <-- send to both broadcasts
                    sock.close()


                    print("✅ Post broadcasted. Your message is now visible to followers.\n")

                elif sub_choice in {"V", "O"}:
                    # Build an index for debugging
                    all_authors = []
                    for p in post_feed:
                        all_authors.append(p.get("user_id", "?"))

                    # Helper: fallback match by display name if USER_ID changed (e.g., IP shift)
                    def is_from_followed(post):
                        if post["user_id"] in following:
                            return True
                        # fallback: match followed users by display name (best-effort)
                        disp = post.get("display_name")
                        # Derive display names for IDs in following
                        followed_display_names = set(
                            profile_data.get(uid, {}).get("display_name", uid.split("@")[0])
                            for uid in following
                        )
                        return disp in followed_display_names

                    if sub_choice == "V":
                        # Only followed (plus your own)
                        filtered_posts = [
                            p for p in post_feed
                            if is_from_followed(p) or p["user_id"] == user["user_id"]
                        ]
                    else:
                        # "O" = View ALL posts (debug)
                        filtered_posts = list(post_feed)

                    if not filtered_posts:
                        print("\n📭 No posts to show with current filter.")
                        # Debug hints:
                        print(f"   Following set size: {len(following)}")
                        if following:
                            print("   Following IDs:")
                            for f in sorted(following):
                                print(f"     - {f}")
                        print(f"   Total posts received: {len(post_feed)}")
                        if post_feed:
                            print("   Sample authors seen:")
                            for a in sorted(set(all_authors))[:10]:
                                print(f"     - {a}")
                        print()
                        continue

                    # Show posts
                    while True:
                        now = int(time.time())
                        print("\n==== LSNP Post Feed ====\n")
                        post_keys = {}

                        for idx, post in enumerate(filtered_posts, start=1):
                            age = max(0, now - int(post.get("timestamp", now)))
                            liked = user["user_id"] in post["likes"]
                            print(f"[{idx}] ({age}s ago) {post['display_name']} ({post['user_id']})")
                            print(f"📝 {post['content']}")
                            print(f"❤️ Likes: {len(post['likes'])} – Press [{'U' if liked else 'L'}{idx}] to {'unlike' if liked else 'like'}\n")
                            post_keys[f"{'U' if liked else 'L'}{idx}"] = post

                        print("========================")
                        sub = input("\n[L#/U#] Like/Unlike post | [B] Back\n").strip().upper()

                        if sub == "B":
                            break

                        post = post_keys.get(sub)
                        if not post:
                            print("❌ Invalid post number.")
                            continue

                        if sub.startswith("L") or sub.startswith("U"):
                            is_like = sub.startswith("L")
                            action = "LIKE" if is_like else "UNLIKE"

                            post = post_keys.get(sub)
                            if not post:
                                print("❌ Invalid post number.")
                                continue

                            author_uid = post["user_id"]
                            post_ts = int(post["timestamp"])
                            ts_now = int(time.time())
                            like_msg_id = uuid.uuid4().hex[:8]  # for dedupe
                            token = f"{user['user_id']}|{ts_now+3600}|broadcast"  # per RFC

                            like_fields = {
                                "TYPE": "LIKE",
                                "FROM": user["user_id"],
                                "TO": author_uid,
                                "POST_TIMESTAMP": post_ts,
                                "ACTION": action,          # LIKE or UNLIKE
                                "TIMESTAMP": ts_now,
                                "MESSAGE_ID": like_msg_id, # <-- add this
                                "TOKEN": token,
                            }
                            like_msg = build_message(like_fields)

                            # 1) Unicast to author (so they can notify/ack if needed)
                            _send_unicast(like_msg, author_uid, user["verbose"])

                            # 2) Broadcast so all peers (including ourselves) update counts
                            bsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                            bsock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                            _broadcast_to_all(bsock, like_msg.encode("utf-8"))
                            bsock.close()

                            # Optimistic UI update for our local view
                            if is_like:
                                post["likes"].add(user["user_id"])
                                print("❤️ You liked the post.\n")
                            else:
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
                    show_recent_messages(target_uid, count=20)

                else:
                    print(f"❌ Failed to send message to {target_display}")
                    if target_uid not in user_ip_map:
                        print("   No IP address known for target. Wait for their ping/profile.")
                    else:
                        print(f"   Target IP: {user_ip_map[target_uid]}")


        elif choice == "6":
            # === Tic Tac Toe Menu ===
            def render_board(b):
                def c(i): return b[i] if b[i] else " "
                print(f"\n {c(0)} | {c(1)} | {c(2)}\n-----------\n {c(3)} | {c(4)} | {c(5)}\n-----------\n {c(6)} | {c(7)} | {c(8)}\n")

            while True:
                now = time.time()
                active = [uid for uid, last in peer_table.items() if now - last < 60 and uid != user["user_id"]]

                # Build status list
                items = []
                for uid in active:
                    has_inv = any(k[0] == uid for k in ttt_invites.keys())
                    ongoing = any(uid in g.get("players", {}).values() for g in ttt_games.values())
                    status = []
                    if has_inv: status.append("Has Invite")
                    if ongoing: status.append("Ongoing")
                    items.append((uid, ", ".join(status) if status else "Idle"))

                print("\n=== Tic Tac Toe ===")
                print("[N] New game  [B] Back")
                if not items:
                    print("No active peers.")
                else:
                    for i,(uid,st) in enumerate(items,1):
                        disp = profile_data.get(uid, {}).get("display_name", uid.split("@")[0])
                        print(f"[{i}] {disp} ({uid}) {f'({st})' if st else ''}")

                sel = input("Pick user #, or N/B: ").strip().upper()
                if sel == "B":
                    break
                if sel == "N":
                    if not active:
                        print("No peers to invite."); continue
                    try:
                        # choose opponent
                        for i, uid in enumerate(active,1):
                            disp = profile_data.get(uid, {}).get("display_name", uid.split("@")[0])
                            print(f"[{i}] {disp} ({uid})")
                        j = int(input("Invite which #? ").strip())
                        opp = active[j-1]
                    except Exception:
                        print("Invalid."); continue
                    sym = input("Play as X or O? [X/O]: ").strip().upper() or "X"
                    if sym not in {"X","O"}:
                        print("Symbol must be X or O."); continue
                    ts = int(time.time())
                    token_game = f"{user['user_id']}|{ts+3600}|game"
                    gid = start_game_invite(user["user_id"], opp, sym, token_game, verbose=user["verbose"])
                    if gid:
                        print(f"Invite sent for game {gid}.")
                    else:
                        print("Invite failed to send.")
                    continue

                # numeric selection -> open user context
                try:
                    idx = int(sel) - 1
                    if idx < 0 or idx >= len(items): raise ValueError
                except Exception:
                    print("Invalid selection."); continue

                target_uid = items[idx][0]
                disp = profile_data.get(target_uid, {}).get("display_name", target_uid.split("@")[0])
                print(f"\n== {disp} ==")

                # Case 1: there is an invite from this user
                invite_key = next((k for k in ttt_invites.keys() if k[0] == target_uid), None)
                if invite_key:
                    inv = ttt_invites[invite_key]
                    gid = inv["gameid"]; inviter_symbol = inv["symbol"]
                    my_symbol = "O" if inviter_symbol == "X" else "X"
                    print(f"Invite detected (game {gid}). You are '{my_symbol}'.")
                    move = input("Enter your first move [0-8] to ACCEPT, or 'n' to reject: ").strip().lower()
                    if move == "n":
                        del ttt_invites[invite_key]
                        print("Invite rejected.")
                        continue
                    try:
                        pos = int(move)
                    except ValueError:
                        print("Invalid input."); continue
                    # ensure game exists locally
                    if gid not in ttt_games:
                        ttt_games[gid] = {"board":[""]*9,"players":{inviter_symbol: target_uid, my_symbol: user["user_id"]},
                                        "next_symbol":"X","turn":1,"moves_seen":set()}
                    ts = int(time.time())
                    token_game = f"{user['user_id']}|{ts+3600}|game"
                    ok = send_move(user["user_id"], target_uid, gid, pos, token_game, verbose=user["verbose"])
                    if ok:
                        print(f"Accepted invite. Played {pos}.")
                        del ttt_invites[invite_key]
                        render_board(ttt_games[gid]["board"])
                    else:
                        print("Failed to send your move.")
                    continue

                # Case 2: ongoing game vs this user
                my_games = [ (gid,g) for gid,g in ttt_games.items() if target_uid in g.get("players", {}).values() ]
                if not my_games:
                    print("No invite or ongoing game with this user.")
                    continue

                # If multiple games with same user exist, pick one
                if len(my_games) > 1:
                    print("Multiple games found:")
                    for i,(gid, g) in enumerate(my_games,1):
                        print(f"  [{i}] {gid}")
                    try:
                        k = int(input("Pick game #: ").strip()); gid, game = my_games[k-1]
                    except Exception:
                        print("Invalid."); continue
                else:
                    gid, game = my_games[0]

                b = game["board"]; ns = game["next_symbol"]; turn = game["turn"]
                render_board(b)
                # my symbol
                my_sym = next((s for s,uid in game["players"].items() if uid == user["user_id"]), None)
                if not my_sym:
                    print("You are not a player in this game."); continue

                if ns != my_sym:
                    print(f"Waiting for opponent ({ns}'s turn).")
                    continue

                mv = input(f"Your move as {my_sym} [0-8] (or 'b' to back): ").strip().lower()
                if mv == "b":
                    continue
                try:
                    pos = int(mv)
                except ValueError:
                    print("Invalid."); continue
                ts = int(time.time())
                token_game = f"{user['user_id']}|{ts+3600}|game"
                ok = send_move(user["user_id"], target_uid, gid, pos, token_game, verbose=user["verbose"])
                if not ok:
                    print("Move send failed.")
                else:
                    render_board(ttt_games[gid]["board"])



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
