# handlers/post_handler.py
import time
from state import post_feed, profile_data
from dedupe import seen_before

def handle_post(msg: dict, addr, verbose: bool):
    """Process TYPE: POST (with duplicate suppression by MESSAGE_ID)"""
    user_id = msg.get("USER_ID")
    content = msg.get("CONTENT", "")
    ttl_raw = msg.get("TTL")
    ts_raw = msg.get("TIMESTAMP")
    message_id = msg.get("MESSAGE_ID")

    if seen_before(message_id):
        if verbose:
            print(f"DROP! Duplicate POST (MESSAGE_ID={message_id}) from {addr}")
        return

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
        "timestamp": timestamp,
        "ttl": ttl,
        "likes": set(),
        "message_id": message_id,
    }
    post_feed.append(post)
    if verbose:
        print(f"< POST from {user_id}: {content}")
