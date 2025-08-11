"""Handler for group-related messages."""
import time
from typing import List

from ..models.group import Group, GroupMessage
from ..network.client import NetworkManager
from ..core.state import app_state


class GroupHandler:
    """Handles group-related messages."""
    
    def __init__(self, network_manager: NetworkManager, verbose: bool = False):
        self.network_manager = network_manager
        self.verbose = verbose
    
    def handle_group_create(self, msg: dict, addr: tuple) -> None:
        """Handle a GROUP_CREATE message."""
        from_user = msg.get("FROM")
        group_id = msg.get("GROUP_ID")
        group_name = msg.get("GROUP_NAME")
        members_str = msg.get("MEMBERS", "")
        timestamp = float(msg.get("TIMESTAMP", time.time()))
        
        if not all([from_user, group_id, group_name]):
            if self.verbose:
                print("GROUP_CREATE missing required fields")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(from_user, addr[0])
        
        # Parse members list
        members = set()
        if members_str:
            members = set(member.strip() for member in members_str.split(",") if member.strip())
        
        # Create group
        group = Group(
            group_id=group_id,
            group_name=group_name,
            creator=from_user,
            members=members,
            created_timestamp=timestamp
        )
        
        # Add to state
        app_state.add_group(group)
        
        if self.verbose:
            print(f"GROUP_CREATE: {from_user} created group {group_name} ({group_id})")
    
    def handle_group_update(self, msg: dict, addr: tuple) -> None:
        """Handle a GROUP_UPDATE message."""
        from_user = msg.get("FROM")
        group_id = msg.get("GROUP_ID")
        add_str = msg.get("ADD", "")
        remove_str = msg.get("REMOVE", "")
        
        if not all([from_user, group_id]):
            if self.verbose:
                print("GROUP_UPDATE missing required fields")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(from_user, addr[0])
        
        # Get the group
        group = app_state.get_group(group_id)
        if not group:
            if self.verbose:
                print(f"GROUP_UPDATE: Group {group_id} not found")
            return
        
        # Parse member changes
        add_members = []
        remove_members = []
        
        if add_str:
            add_members = [member.strip() for member in add_str.split(",") if member.strip()]
        
        if remove_str:
            remove_members = [member.strip() for member in remove_str.split(",") if member.strip()]
        
        # Update group membership
        app_state.update_group_membership(group_id, add_members, remove_members)
        
        if self.verbose:
            print(f"GROUP_UPDATE: {from_user} updated group {group.group_name}")
            if add_members:
                print(f"  Added: {', '.join(add_members)}")
            if remove_members:
                print(f"  Removed: {', '.join(remove_members)}")
    
    def handle_group_message(self, msg: dict, addr: tuple) -> None:
        """Handle a GROUP_MESSAGE message."""
        from_user = msg.get("FROM")
        group_id = msg.get("GROUP_ID")
        content = msg.get("CONTENT", "")
        timestamp = float(msg.get("TIMESTAMP", time.time()))
        
        if not all([from_user, group_id, content]):
            if self.verbose:
                print("GROUP_MESSAGE missing required fields")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(from_user, addr[0])
        
        # Get the group
        group = app_state.get_group(group_id)
        if not group:
            if self.verbose:
                print(f"GROUP_MESSAGE: Group {group_id} not found")
            return
        
        # Get display name
        peer = app_state.get_peer(from_user)
        display_name = peer.display_name if peer else from_user.split("@")[0]
        
        # Create group message
        group_message = GroupMessage(
            from_user=from_user,
            group_id=group_id,
            content=content,
            timestamp=timestamp,
            display_name=display_name
        )
        
        # Add to history
        app_state.add_group_message(group_message)
        
        if self.verbose:
            print(f"GROUP_MESSAGE: {from_user} sent message to group {group.group_name}")
