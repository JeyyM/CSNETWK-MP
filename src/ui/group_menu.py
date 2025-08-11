"""Group management UI."""
from typing import List, Optional

from .components import show_separator, get_choice
from ..models.user import User, Peer
from ..models.group import Group, GroupMessage
from ..services.group_service import GroupService
from ..services.user_service import UserService
from ..core.state import app_state


class GroupMenu:
    """UI for group management."""
    
    def __init__(self, user: User, group_service: GroupService, user_service: UserService):
        self.user = user
        self.group_service = group_service
        self.user_service = user_service
    
    def show_group_menu(self) -> None:
        """Show group management interface."""
        while True:
            choice = input(
                "\n[C] Create Group\n[L] List My Groups\n[M] Send Group Message\n[V] View Group Messages\n[B] Back to Main Menu\nSelect: "
            ).strip().upper()
            
            if choice == "C":
                self._create_group()
            elif choice == "L":
                self._list_groups()
            elif choice == "M":
                self._send_group_message()
            elif choice == "V":
                self._view_group_messages()
            elif choice == "B":
                break
            else:
                print("Invalid option.\n")
    
    def _create_group(self) -> None:
        """Create a new group."""
        group_id = input("Enter group ID (unique identifier): ").strip()
        if not group_id:
            print("Group ID cannot be empty.\n")
            return
        
        # Check if group already exists
        if self.group_service.get_group(group_id):
            print("Group with this ID already exists.\n")
            return
        
        group_name = input("Enter group name: ").strip()
        if not group_name:
            print("Group name cannot be empty.\n")
            return
        
        # Get active peers for member selection
        peers = self.user_service.get_active_peers(self.user.user_id)
        if not peers:
            print("No active peers found to add to group.\n")
            return
        
        print("\nSelect members to add to the group:")
        for i, peer in enumerate(peers, 1):
            print(f"[{i}] {peer.display_name} ({peer.user_id})")
        
        print("\nEnter member numbers separated by commas (e.g., 1,3,5):")
        member_input = input("Members: ").strip()
        
        if not member_input:
            print("At least one member must be selected.\n")
            return
        
        # Parse selected members
        try:
            selected_indices = [int(x.strip()) - 1 for x in member_input.split(",")]
            selected_members = []
            
            for idx in selected_indices:
                if 0 <= idx < len(peers):
                    selected_members.append(peers[idx].user_id)
                else:
                    print(f"Invalid member number: {idx + 1}")
                    return
            
            # Add creator to members list
            all_members = selected_members + [self.user.user_id]
            
            # Create the group
            success = self.group_service.create_group(group_id, group_name, all_members, self.user)
            
            if success:
                print(f"   Group '{group_name}' created successfully!")
                print(f"   Group ID: {group_id}")
                print(f"   Members: {len(all_members)}")
            else:
                print("Failed to create group. Some members may not have received the invitation.")
            
        except ValueError:
            print("Invalid input. Please enter numbers separated by commas.\n")
    
    def _list_groups(self) -> None:
        """List all groups the user is a member of."""
        groups = self.group_service.get_user_groups(self.user.user_id)
        
        if not groups:
            print("\nYou are not a member of any groups.\n")
            return
        
        print("\n==== Your Groups ====")
        for i, group in enumerate(groups, 1):
            creator_peer = app_state.get_peer(group.creator)
            creator_name = creator_peer.display_name if creator_peer else group.creator.split("@")[0]
            role = "Creator" if group.is_creator(self.user.user_id) else "Member"
            
            print(f"[{i}] {group.group_name} (ID: {group.group_id})")
            print(f"    Role: {role}")
            print(f"    Creator: {creator_name}")
            print(f"    Members: {group.member_count}")
            
            # Show recent message count
            messages = self.group_service.get_group_messages(group.group_id)
            if messages:
                print(f"    Messages: {len(messages)} (latest: {messages[-1].format_for_display()[:50]}...)")
            else:
                print(f"    Messages: 0")
            print()
        
        print("===================\n")
    
    def _send_group_message(self) -> None:
        """Send a message to a group."""
        groups = self.group_service.get_user_groups(self.user.user_id)
        
        if not groups:
            print("\nYou are not a member of any groups.\n")
            return
        
        print("\nSelect a group to send message to:")
        for i, group in enumerate(groups, 1):
            print(f"[{i}] {group.group_name} ({group.member_count} members)")
        
        choice = input("\nSelect group number: ").strip()
        try:
            group_index = int(choice) - 1
            if 0 <= group_index < len(groups):
                selected_group = groups[group_index]
                
                content = input(f"Enter message for '{selected_group.group_name}': ").strip()
                if not content:
                    print("Message cannot be empty.\n")
                    return
                
                success = self.group_service.send_group_message(selected_group.group_id, content, self.user)
                
                if success:
                    print(f"Message sent to '{selected_group.group_name}'!\n")
                else:
                    print("Failed to send message to some group members.\n")
            else:
                print("Invalid group selection.\n")
        except ValueError:
            print("Invalid input. Please enter a number.\n")
    
    def _view_group_messages(self) -> None:
        """View messages from a group."""
        groups = self.group_service.get_user_groups(self.user.user_id)
        
        if not groups:
            print("\nYou are not a member of any groups.\n")
            return
        
        print("\nSelect a group to view messages:")
        for i, group in enumerate(groups, 1):
            message_count = len(self.group_service.get_group_messages(group.group_id))
            print(f"[{i}] {group.group_name} ({message_count} messages)")
        
        choice = input("\nSelect group number: ").strip()
        try:
            group_index = int(choice) - 1
            if 0 <= group_index < len(groups):
                selected_group = groups[group_index]
                self._show_group_conversation(selected_group)
            else:
                print("Invalid group selection.\n")
        except ValueError:
            print("Invalid input. Please enter a number.\n")
    
    def _show_group_conversation(self, group: Group) -> None:
        """Show conversation for a specific group."""
        messages = self.group_service.get_group_messages(group.group_id)
        
        print(f"\n==== {group.group_name} Messages ====")
        if not messages:
            print("No messages in this group yet.\n")
        else:
            # Show recent messages (last 20)
            recent_messages = messages[-20:] if len(messages) > 20 else messages
            
            if len(messages) > 20:
                print(f"... showing last 20 of {len(messages)} messages ...\n")
            
            for message in recent_messages:
                print(message.format_for_display())
        
        print("=" * 40)
        print()
