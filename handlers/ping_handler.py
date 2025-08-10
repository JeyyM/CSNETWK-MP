# handlers/ping_handler.py
import time
from protocol import build_message
from state import peer_table, user_ip_map, profile_data
import socket

PORT = 50999

def _send_profile_unicast(to_ip: str, user_id: str, display_name: str, status: str, verbose=False):
    fields = {
        "TYPE": "PROFILE",
        "USER_ID": user_id,
        "DISPLAY_NAME": display_name,
        "STATUS": status,
    }
    msg = build_message(fields).encode("utf-8")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.sendto(msg, (to_ip, PORT))
        if verbose:
            print(f"[DEBUG] Sent PROFILE (unicast) to {(to_ip, PORT)}")
    finally:
        s.close()

def handle_ping(msg: dict, addr, verbose: bool):
    user_id = msg.get("USER_ID")
    if not user_id:
        if verbose: print("[DEBUG] PING missing USER_ID")
        return

    peer_table[user_id] = time.time()
    user_ip_map[user_id] = addr[0]
    if verbose:
        print(f"📡 PING from {user_id} at {addr[0]}")

    # Optional friendly reply: if we have a 'me' profile recorded, unicast our PROFILE back
    for uid, pdata in profile_data.items():
        if pdata.get("is_me"):
            _send_profile_unicast(addr[0], uid, pdata.get("display_name", "Me"), pdata.get("status", ""), verbose)
            break
