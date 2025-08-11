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
        # Dedupe
        mid = msg.get("MESSAGE_ID")
        if seen_before(mid):
            return

        # Parse fields (POST uses USER_ID, not FROM)
        user_id = msg.get("USER_ID", "")
        content = msg.get("CONTENT", "")
        try:
            ts = int(msg.get("TIMESTAMP", str(int(time.time()))))
        except Exception:
            ts = int(time.time())
        try:
            ttl = int(msg.get("TTL", "3600"))
        except Exception:
            ttl = 3600

        # TTL drop (optional but helpful)
        if ts + ttl < int(time.time()):
            if self.verbose:
                print(f"[POST] DROP expired POST (mid={mid}) from {user_id}")
            return

        # Resolve display name from peer table if known
        peer = app_state.get_peer(user_id)
        display_name = peer.display_name if peer else (user_id.split("@")[0] or user_id)

        # Persist to feed (followers filter happens when reading)
        app_state.add_post(Post(
            user_id=user_id,
            display_name=display_name,
            content=content,
            timestamp=ts,
            message_id=mid or "",
            likes=set(),
            ttl=ttl,
        ))

        if self.verbose:
            print(f"RECV< POST by {display_name}: {content}")