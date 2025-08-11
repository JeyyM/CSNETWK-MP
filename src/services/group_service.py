"""Group service for group management operations."""
import time
import uuid
from typing import List, Optional

from ..models.user import User
from ..models.group import Group, GroupMessage
from ..network.client import NetworkManager
from ..network.protocol import build_message
from ..core.state import app_state


class GroupService:
    """Service for group-related operations."""
    
    def __init__(self, network_manager: NetworkManager):
        self.network_manager = network_manager
    
    def create_group(self, group_id: str, group_name: str, members: List[str], user: User) -> bool:
        """Create a new group and broadcast to all members."""
        # Create group locally
        group = Group(
            group_id=group_id,
            group_name=group_name,
            creator=user.user_id,
            members=set(members),
            created_timestamp=time.time()
        )
        
        # Ensure creator is in the group
        group.add_member(user.user_id)
        
        # Add to state
        app_state.add_group(group)
        
        # Broadcast GROUP_CREATE to all members
        timestamp = int(time.time())
        token = f"{user.user_id}|{timestamp+3600}|group"
        
        fields = {
            "TYPE": "GROUP_CREATE",
            "FROM": user.user_id,
            "GROUP_ID": group_id,
            "GROUP_NAME": group_name,
            "MEMBERS": ",".join(members),
            "TIMESTAMP": timestamp,
            "TOKEN": token,
        }
        
        create_msg = build_message(fields)
        
        # Send to all members
        success = True
        for member_id in group.members:
            if member_id != user.user_id:  # Don't send to self
                if not self.network_manager.send_unicast(create_msg, member_id):
                    success = False
        
        return success
    
    def update_group(self, group_id: str, add_members: List[str] = None, remove_members: List[str] = None, user: User = None) -> bool:
        """Update group membership and broadcast to all members."""
        group = app_state.get_group(group_id)
        if not group:
            return False
        
        # Check if user is authorized (creator or existing member)
        if user and not (group.is_creator(user.user_id) or group.is_member(user.user_id)):
            return False
        
        # Update local state
        if not app_state.update_group_membership(group_id, add_members, remove_members):
            return False
        
        # Broadcast GROUP_UPDATE to all current members
        timestamp = int(time.time())
        token = f"{user.user_id}|{timestamp+3600}|group" if user else ""
        
        fields = {
            "TYPE": "GROUP_UPDATE",
            "FROM": user.user_id if user else "",
            "GROUP_ID": group_id,
            "TIMESTAMP": timestamp,
            "TOKEN": token,
        }
        
        if add_members:
            fields["ADD"] = ",".join(add_members)
        if remove_members:
            fields["REMOVE"] = ",".join(remove_members)
        
        update_msg = build_message(fields)
        
        # Send to all current members (including newly added ones)
        updated_group = app_state.get_group(group_id)
        if updated_group:
            for member_id in updated_group.members:
                if user and member_id != user.user_id:  # Don't send to self
                    self.network_manager.send_unicast(update_msg, member_id)
        
        return True
    
    def send_group_message(self, group_id: str, content: str, user: User) -> bool:
        """Send a message to a group."""
        group = app_state.get_group(group_id)
        if not group:
            return False
        
        # Check if user is a member
        if not group.is_member(user.user_id):
            return False
        
        timestamp = int(time.time())
        token = f"{user.user_id}|{timestamp+3600}|group"
        
        fields = {
            "TYPE": "GROUP_MESSAGE",
            "FROM": user.user_id,
            "GROUP_ID": group_id,
            "CONTENT": content,
            "TIMESTAMP": timestamp,
            "TOKEN": token,
        }
        
        message_text = build_message(fields)
        
        # Send to all group members except self
        success = True
        for member_id in group.members:
            if member_id != user.user_id:
                if not self.network_manager.send_unicast(message_text, member_id):
                    success = False
        
        # Add to local message history
        group_message = GroupMessage(
            from_user=user.user_id,
            group_id=group_id,
            content=content,
            timestamp=timestamp,
            display_name=user.display_name
        )
        app_state.add_group_message(group_message)
        
        return success
    
    def get_group(self, group_id: str) -> Optional[Group]:
        """Get a group by ID."""
        return app_state.get_group(group_id)
    
    def get_user_groups(self, user_id: str) -> List[Group]:
        """Get all groups that a user is a member of."""
        return app_state.get_groups_for_user(user_id)
    
    def get_group_messages(self, group_id: str) -> List[GroupMessage]:
        """Get all messages for a group."""
        return app_state.get_group_messages(group_id)
    
    def get_all_groups(self) -> List[Group]:
        """Get all groups."""
        return app_state.get_all_groups()
