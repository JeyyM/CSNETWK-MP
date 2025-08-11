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
        post_id = msg.get("POST_ID")  # Use POST_ID (MESSAGE_ID)
        action = msg.get("ACTION", "LIKE")
        
        if not from_user or not to_user or not post_id:
            if self.verbose:
                print("LIKE missing required fields")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(from_user, addr[0])
        
        # Find the post by MESSAGE_ID
        post = None
        for p in app_state.get_posts(False):
            if p.message_id == post_id:
                post = p
                break
        if not post:
            if self.verbose:
                print(f"LIKE: Post not found for {to_user} with MESSAGE_ID {post_id}")
            return
        
        # Apply like/unlike
        if action == "LIKE":
            post.add_like(from_user)
            if self.verbose:
                print(f"LIKE: {from_user} liked post {post_id}")
        elif action == "UNLIKE":
            post.remove_like(from_user)
            if self.verbose:
                print(f"UNLIKE: {from_user} unliked post {post_id}")
        else:
            if self.verbose:
                print(f"LIKE: Unknown action {action}")
