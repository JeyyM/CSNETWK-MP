"""Message service for posts and direct messages."""
import time
import uuid
from typing import List, Optional

from ..models.user import User, Post, DirectMessage
from ..network.client import NetworkManager
from ..network.protocol import build_message
from ..core.state import app_state


class MessageService:
    """Service for messaging operations."""
    
    def __init__(self, network_manager: NetworkManager):
        self.network_manager = network_manager
    
    def create_post(self, content: str, user: User) -> bool:
        """Create and broadcast a new post."""
        message_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        ttl = 3600
        token = f"{user.user_id}|{timestamp+ttl}|broadcast"

        fields = {
            "TYPE": "POST",
            "USER_ID": user.user_id,
            "CONTENT": content,
            "TIMESTAMP": timestamp,
            "TTL": ttl,
            "MESSAGE_ID": message_id,
            "TOKEN": token,
        }
        post_msg = build_message(fields)
        self.network_manager.send_broadcast(post_msg)
        return True
    
    def like_post(self, post: Post, user: User, is_like: bool = True) -> bool:
        """Like or unlike a post."""
        action = "LIKE" if is_like else "UNLIKE"
        timestamp = int(time.time())
        message_id = uuid.uuid4().hex[:8]
        token = f"{user.user_id}|{timestamp+3600}|broadcast"

        like_fields = {
            "TYPE": "LIKE",
            "FROM": user.user_id,
            "TO": post.user_id,
            "POST_TIMESTAMP": int(post.timestamp),
            "ACTION": action,
            "TIMESTAMP": timestamp,
            "MESSAGE_ID": message_id,
            "TOKEN": token,
        }
        like_msg = build_message(like_fields)

        # Send to author
        self.network_manager.send_unicast(like_msg, post.user_id)
        
        # Broadcast to all peers
        self.network_manager.send_broadcast(like_msg)

        # Update local state optimistically
        if is_like:
            post.add_like(user.user_id)
        else:
            post.remove_like(user.user_id)

        return True
    
    def send_direct_message(self, content: str, to_user_id: str, user: User) -> bool:
        """Send a direct message to a user."""
        message_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        token = f"{user.user_id}|{timestamp+300}|chat"

        fields = {
            "TYPE": "DM",
            "FROM": user.user_id,
            "TO": to_user_id,
            "CONTENT": content,
            "TIMESTAMP": timestamp,
            "MESSAGE_ID": message_id,
            "TOKEN": token,
        }
        dm_msg = build_message(fields)

        success = self.network_manager.send_unicast(dm_msg, to_user_id)
        
        if success:
            # Add to local history
            dm = DirectMessage(
                from_user=user.user_id,
                to_user=to_user_id,
                content=content,
                timestamp=timestamp,
                message_id=message_id,
                display_name=user.display_name
            )
            # Note: For outgoing messages, we store them under the recipient's ID
            # This is handled in the UI layer for proper display
        
        return success
    
    def get_posts(self, filter_followed: bool = False, user_id: Optional[str] = None) -> List[Post]:
        """Get posts from the feed."""
        return app_state.get_posts(filter_followed, user_id)
    
    def get_dm_history(self, user_id: str) -> List[DirectMessage]:
        """Get direct message history with a user."""
        return app_state.get_dm_history(user_id)
    
    def get_dm_conversations(self) -> dict:
        """Get all DM conversations with message counts."""
        return app_state.get_dm_conversations()
    
    def set_active_dm_user(self, user_id: Optional[str]) -> None:
        """Set the active DM user."""
        app_state.set_active_dm_user(user_id)
    
    def get_active_dm_user(self) -> Optional[str]:
        """Get the active DM user."""
        return app_state.get_active_dm_user()
