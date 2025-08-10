"""Handler for POST messages."""
import time

from ..models.user import Post, Peer
from ..core.state import app_state


class PostHandler:
    """Handles POST messages."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def handle(self, msg: dict, addr: tuple) -> None:
        """Handle a POST message."""
        user_id = msg.get("USER_ID")
        content = msg.get("CONTENT", "")
        timestamp = float(msg.get("TIMESTAMP", time.time()))
        message_id = msg.get("MESSAGE_ID", "")
        ttl = int(msg.get("TTL", 3600))
        
        if not user_id or not content:
            if self.verbose:
                print("POST missing USER_ID or CONTENT")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(user_id, addr[0])
        
        # Get display name
        peer = app_state.get_peer(user_id)
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
        
        if self.verbose:
            print(f"POST from {display_name}: {content[:50]}...")
