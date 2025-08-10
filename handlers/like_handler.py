# handlers/like_handler.py
from state import post_feed, profile_data
from dedupe import seen_before

def handle_like(msg: dict, addr, verbose: bool):
    """
    Process TYPE: LIKE or UNLIKE.
    Update matching post (author == TO and timestamp == POST_TIMESTAMP) for all peers.
    """
    liker_uid = msg.get("FROM")
    author_uid = msg.get("TO")
    post_ts_raw = msg.get("POST_TIMESTAMP")
    action = (msg.get("ACTION") or "").upper()
    message_id = msg.get("MESSAGE_ID")

    if seen_before(message_id):
        if verbose:
            print(f"DROP! Duplicate LIKE (MESSAGE_ID={message_id}) from {addr}")
        return

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

    target = None
    for p in post_feed:
        if p.get("user_id") == author_uid and int(p.get("timestamp", -1)) == post_ts:
            target = p
            break

    if not target:
        if verbose:
            print("[DEBUG] LIKE referenced post not found locally")
        return

    if action == "LIKE":
        target["likes"].add(liker_uid)
    else:
        target["likes"].discard(liker_uid)

    if verbose:
        liker_name = profile_data.get(liker_uid, {}).get("display_name", liker_uid.split("@")[0])
        print(f"💌 LIKE update: {liker_name} {action.lower()}d post ts={post_ts}")
