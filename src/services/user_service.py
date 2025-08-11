"""User management service."""
import time
import uuid
from typing import List, Optional

from ..models.user import User, Peer
from ..network.client import NetworkManager, get_local_ip
from ..network.protocol import build_message
from ..core.state import app_state


class UserService:
    """Service for user-related operations."""
    
    def __init__(self, network_manager: NetworkManager):
        self.network_manager = network_manager
    
    def create_user(self, username: str, display_name: str, status: str, verbose: bool = False) -> User:
        """Create a new user."""
        ip = get_local_ip()
        return User.create(username, display_name, status, ip, verbose)
    
    def broadcast_profile(self, user: User) -> None:
        """Broadcast user profile to network."""
        fields = {
            "TYPE": "PROFILE",
            "USER_ID": user.user_id,
            "DISPLAY_NAME": user.display_name,
            "STATUS": user.status,
        }
        profile_msg = build_message(fields)
        self.network_manager.send_broadcast(profile_msg)
    
    def follow_user(self, user_id: str, from_user: User) -> bool:
        """Send follow request to a user."""
        message_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        ttl = 3600
        token = f"{from_user.user_id}|{timestamp+ttl}|follow"

        fields = {
            "TYPE": "FOLLOW",
            "MESSAGE_ID": message_id,
            "FROM": from_user.user_id,
            "TO": user_id,
            "TIMESTAMP": timestamp,
            "TOKEN": token,
        }
        follow_msg = build_message(fields)
        self.network_manager.send_broadcast(follow_msg)
        success = self.network_manager.send_unicast(follow_msg, user_id)
        
        if success:
            app_state.follow_user(user_id)
        
        return success
    
    def unfollow_user(self, user_id: str, from_user: User) -> bool:
        """Send unfollow request to a user."""
        message_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        ttl = 3600
        token = f"{from_user.user_id}|{timestamp+ttl}|follow"

        fields = {
            "TYPE": "UNFOLLOW",
            "MESSAGE_ID": message_id,
            "FROM": from_user.user_id,
            "TO": user_id,
            "TIMESTAMP": timestamp,
            "TOKEN": token,
        }
        unfollow_msg = build_message(fields)
        self.network_manager.send_broadcast(unfollow_msg)
        success = self.network_manager.send_unicast(unfollow_msg, user_id)
        
        if success:
            app_state.unfollow_user(user_id)
        
        return success
    
    def get_active_peers(self, exclude_user_id: Optional[str] = None) -> List[Peer]:
        """Get all active peers."""
        return app_state.get_active_peers(exclude_user_id)
    
    def get_peer(self, user_id: str) -> Optional[Peer]:
        """Get a specific peer."""
        return app_state.get_peer(user_id)
