"""Handler for POST messages."""
import time

from ..models.user import Post, Peer
from ..core.state import app_state
from ..utils.dedupe import seen_before  # <-- add this
from ..network.protocol import build_message

class PostHandler:
    """Handles POST messages."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
    # post_handler.py
    def handle(self, msg: dict, addr: tuple) -> None:
        import time
        user_id = msg.get("USER_ID")
        content = msg.get("CONTENT", "")
        timestamp = float(msg.get("TIMESTAMP", time.time()))
        message_id = msg.get("MESSAGE_ID", "")
        ttl = int(msg.get("TTL", 3600))

        if not user_id or not content:
            if self.verbose:
                print("POST missing USER_ID or CONTENT")
            return

        # (optional) dedupe is fine to keep
        # if message_id and seen_before(message_id): return

        # update IP mapping
        app_state.update_peer_ip(user_id, addr[0])

        # accept if it's our own post; otherwise only if we follow the author
        me = getattr(app_state, "_local_user_id", None)
        if me and user_id != me and not app_state.is_following(user_id):
            if self.verbose:
                print(f"[DEBUG] Ignored POST from non-followed user {user_id}")
            return

        peer = app_state.get_peer(user_id)
        display_name = peer.display_name if peer else (user_id.split("@")[0] if "@" in user_id else user_id)

        app_state.add_post(
            Post(
                user_id=user_id,
                display_name=display_name,
                content=content,
                timestamp=timestamp,
                message_id=message_id,
                likes=set(),
                ttl=ttl,
            )
        )
        if self.verbose:
            t = time.strftime("%H:%M:%S", time.localtime())
            print(f"SAVE  {t} POST from {display_name} ({user_id})")
