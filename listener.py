# listener.py (modular, RFC-safe parsing & routing)
import socket
import time

from protocol import parse_message
from state import peer_table, profile_data, user_ip_map, post_feed

from handlers.ping_handler import handle_ping
from handlers.profile_handler import handle_profile
from handlers.dm_handler import handle_dm
from handlers.post_handler import handle_post
from handlers.like_handler import handle_like
from handlers.tictactoe_handler import (
    handle_tictactoe_invite, handle_tictactoe_move, handle_tictactoe_result
)

PORT = 50999
BUFFER_SIZE = 65535
LISTEN_IP = ''

def start_listener(verbose: bool = False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # receive broadcasts

    # bind with simple retry
    for retry in range(5):
        try:
            sock.bind((LISTEN_IP, PORT))
            break
        except OSError as e:
            if retry == 4:
                print(f"❌ Failed to bind to port {PORT} after 5 attempts: {e}")
                return
            print(f"⚠️  Retry {retry + 1}: Failed to bind to port {PORT}, retrying in 1 second...")
            time.sleep(1)

    print(f"[INFO] Listening on UDP port {PORT}...")

    try:
        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                raw = data.decode("utf-8", errors="ignore")
            except Exception as e:
                if verbose:
                    print(f"⚠️  Receive error: {e}")
                continue

            msg = parse_message(raw)
            if not msg:
                if verbose:
                    print(f"DROP! Invalid or unterminated message from {addr}.")
                continue

            if verbose:
                t = time.strftime("%H:%M:%S")
                print(f"\nRECV< {t} {addr[0]}:{addr[1]} TYPE={msg.get('TYPE','?')}")

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
            elif mtype == "TICTACTOE_INVITE":
                handle_tictactoe_invite(msg, addr, sock, verbose)
            elif mtype == "TICTACTOE_MOVE":
                handle_tictactoe_move(msg, addr, sock, verbose)
            elif mtype == "TICTACTOE_RESULT":
                handle_tictactoe_result(msg, addr, sock, verbose)


    except KeyboardInterrupt:
        print("\n[INFO] Listener stopped.")
    finally:
        sock.close()

# Re-export these so main.py's existing imports keep working
__all__ = ["start_listener", "peer_table", "profile_data", "user_ip_map", "post_feed"]
