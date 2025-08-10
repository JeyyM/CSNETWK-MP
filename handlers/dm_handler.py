# handlers/dm_handler.py
from protocol import build_message
from state import user_ip_map, profile_data
from shared_state import dm_history, active_dm_user
import socket

PORT = 50999

def handle_dm(msg: dict, addr, verbose: bool):
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

    # Display name fallback
    sender_display = profile_data.get(from_user, {}).get("display_name") or (
        from_user.split("@")[0] if "@" in from_user else from_user
    )

    dm_history.setdefault(from_user, []).append(f"{sender_display}: {content}")

    if active_dm_user == from_user:
        print(f"\n💬 {sender_display}: {content}")
        print(f"[You → {sender_display}]: ", end="", flush=True)
    else:
        print(f"\n💬 New message from {sender_display}: {content}")
        print("> ", end="", flush=True)

    if message_id:
        _send_ack(message_id, addr, verbose)

def _send_ack(message_id: str, addr, verbose: bool):
    ack_fields = {"TYPE": "ACK", "MESSAGE_ID": message_id, "STATUS": "RECEIVED"}
    ack_msg = build_message(ack_fields).encode("utf-8")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.sendto(ack_msg, addr)
        if verbose:
            print(f"✅ Sent ACK for {message_id} to {addr}")
    finally:
        s.close()
