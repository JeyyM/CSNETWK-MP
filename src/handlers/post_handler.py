"""Handler for POST messages."""
import time
from ..models.user import Post
from ..core.state import app_state
from ..utils.dedupe import seen_before

class PostHandler:
    """Handles POST messages."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def handle(self, msg: dict, addr: tuple) -> None:
        """Handle a POST message."""
        # Dedupe on MESSAGE_ID
        mid = msg.get("MESSAGE_ID", "")
        if seen_before(mid):
            if self.verbose:
                print(f"[POST] Dropping duplicate message {mid}")
            return

        user_id = msg.get("USER_ID", "").strip()
        content = msg.get("CONTENT", "")

        # Basic validation
        if not user_id or not content:
            if self.verbose:
                print("[POST] Invalid post - missing USER_ID or CONTENT")
            return

        # Get TTL (default 3600)
        try:
            ttl = int(msg.get("TTL", 3600))
        except Exception:
            ttl = 3600

        # Use receiver's time for timestamp
        ts = int(time.time())
        
        # Get display name from peer or fallback
        peer = app_state.get_peer(user_id)
        display_name = peer.display_name if peer else (
            user_id.split("@")[0] if "@" in user_id else user_id
        )

        # Create and store post
        post = Post(
            user_id=user_id,
            display_name=display_name,
            content=content,
            timestamp=ts,
            message_id=mid,
            likes=set(),
            ttl=ttl
        )
        app_state.add_post(post)

        if self.verbose:
            print(f"[POST] Added post from {display_name}: {content[:30]}...")