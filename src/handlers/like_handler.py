"""Handler for LIKE messages."""
from ..core.state import app_state


class LikeHandler:
    """Handles LIKE messages."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def handle(self, msg: dict, addr: tuple) -> None:
        """Handle a LIKE message."""
        from_user = msg.get("FROM")
        to_user = msg.get("TO")
        post_timestamp = msg.get("POST_TIMESTAMP")
        action = msg.get("ACTION", "LIKE")
        
        if not from_user or not to_user or not post_timestamp:
            if self.verbose:
                print("LIKE missing required fields")
            return
        
        try:
            post_timestamp = float(post_timestamp)
        except (ValueError, TypeError):
            if self.verbose:
                print("LIKE invalid POST_TIMESTAMP")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(from_user, addr[0])
        
        # Find the post
        post = app_state.find_post(to_user, post_timestamp)
        if not post:
            if self.verbose:
                print(f"LIKE: Post not found for {to_user} at {post_timestamp}")
            return
        
        # Apply like/unlike
        if action == "LIKE":
            post.add_like(from_user)
            if self.verbose:
                print(f"LIKE: {from_user} liked post by {to_user}")
        elif action == "UNLIKE":
            post.remove_like(from_user)
            if self.verbose:
                print(f"UNLIKE: {from_user} unliked post by {to_user}")
        else:
            if self.verbose:
                print(f"LIKE: Unknown action {action}")
