# handlers/profile_handler.py
import time
from state import peer_table, profile_data, user_ip_map

def handle_profile(msg: dict, addr, verbose: bool):
    user_id = msg.get("USER_ID")
    if not user_id:
        if verbose: print("[DEBUG] PROFILE missing USER_ID")
        return

    display_name = msg.get("DISPLAY_NAME", "Unknown")
    status = msg.get("STATUS", "No status")

    profile_data[user_id] = {"display_name": display_name, "status": status}
    peer_table[user_id] = time.time()
    user_ip_map[user_id] = addr[0]

    if verbose:
        print(f"👤 PROFILE from {user_id} ({display_name}) at {addr[0]}")
