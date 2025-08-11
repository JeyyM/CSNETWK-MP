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
    
    def handle(self, msg: dict, addr: tuple) -> None:
        """Handle a POST message."""
        user_id = msg.get("USER_ID")
        content = msg.get("CONTENT", "")
        # RFC uses Unix seconds; keep as float for safety, but it’s fine if sender sent int.
        timestamp = float(msg.get("TIMESTAMP", time.time()))
        message_id = msg.get("MESSAGE_ID", "")
        ttl = int(msg.get("TTL", 3600))
        
        # --- DEDUPE: drop repeated MESSAGE_IDs ---
        if message_id and seen_before(message_id):
            if self.verbose:
                print(f"[DEBUG] Duplicate POST dropped (MESSAGE_ID={message_id})")
            return

        # --- SELF-ECHO GUARD (optional but useful) ---
        # If you add your own post locally on send, ignore the echoed broadcast.
        if hasattr(app_state, "self_user_id") and user_id == getattr(app_state, "self_user_id"):
            if self.verbose:
                print("[DEBUG] Dropped self-echoed POST")
            return

        if not user_id or not content:
            if self.verbose:
                print("POST missing USER_ID or CONTENT")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(user_id, addr[0])

        # --- FOLLOW FILTER per RFC (non-followers should not receive posts) ---
        # If you maintain a follow graph, check it here. If you don't yet, remove this block.
        try:
            # Expect: app_state.is_following(user_id) or similar; adapt to your API.
            if hasattr(app_state, "should_accept_post_from"):
                if not app_state.should_accept_post_from(user_id):
                    if self.verbose:
                        print(f"[DEBUG] Ignored POST from non-followed user {user_id}")
                    return
        except Exception:
            # If not implemented yet, silently allow.
            pass
        
        # Get display name
        peer: Peer = app_state.get_peer(user_id)
        display_name = peer.display_name if peer else (
            user_id.split("@")[0] if "@" in user_id else user_id
        )
        
        # Create post
        post = Post(
            user_id=user_id,
            display_name=display_name,
            content=content,
            timestamp=timestamp,
            message_id=message_id,
            likes=set(),
            ttl=ttl
        )
        
        # Add to feed
        app_state.add_post(post)
