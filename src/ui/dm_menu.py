"""Direct messaging UI."""
from typing import List, Optional

from .components import show_separator, get_choice
from ..models.user import User, Peer, DirectMessage
from ..services.message_service import MessageService
from ..services.user_service import UserService
from ..core.state import app_state


class DirectMessageMenu:
    """UI for direct messaging."""
    
    def __init__(self, user: User, message_service: MessageService, user_service: UserService):
        self.user = user
        self.message_service = message_service
        self.user_service = user_service
    
    def show_dm_menu(self) -> None:
        """Show direct message interface."""
        peers = self.user_service.get_active_peers(self.user.user_id)
        
        if not peers:
            print("No peers available for DM.\n")
            return
        
        print("\n==== Active Peers for DM ====")
        self._display_peers_for_dm(peers)
        print("=============================\n")
        
        choice = input("Select peer number to DM: ").strip()
        try:
            peer_index = int(choice) - 1
            if 0 <= peer_index < len(peers):
                target_peer = peers[peer_index]
                self._start_dm_chat(target_peer)
            else:
                print("Invalid selection.\n")
        except ValueError:
            print("Invalid selection.\n")
    
    def _display_peers_for_dm(self, peers: List[Peer]) -> None:
        """Display peers available for DM."""
        conversations = self.message_service.get_dm_conversations()
        
        for idx, peer in enumerate(peers, start=1):
            message_count = conversations.get(peer.user_id, 0)
            message_indicator = f" ({message_count} messages)" if message_count > 0 else ""
            print(f"[{idx}] {peer.display_name} ({peer.user_id}){message_indicator}")
    
    def _start_dm_chat(self, target_peer: Peer) -> None:
        """Start a DM chat session with a peer."""
        print(f"\nEntering DM chat with {target_peer.display_name}. Type `/exit` to leave, `/refresh` to see new messages.\n")
        
        # Set active DM user
        self.message_service.set_active_dm_user(target_peer.user_id)
        
        # Display existing chat history
        self._display_dm_history(target_peer)
        
        while True:
            msg_text = input(f"[You -> {target_peer.display_name}]: ").strip()
            
            if msg_text == "/exit":
                print("Exiting DM chat.\n")
                self.message_service.set_active_dm_user(None)
                break
            
            if msg_text == "/refresh":
                print("\nRefreshing chat...\n")
                self._display_dm_history(target_peer)
                continue
            
            if msg_text == "/debug":
                self._show_dm_debug_info(target_peer)
                continue
            
            if not msg_text:
                continue
            
            # Send message
            success = self.message_service.send_direct_message(msg_text, target_peer.user_id, self.user)
            
            if success:
                # Show recent conversation
                self._show_recent_messages(target_peer.user_id, count=20)
            else:
                print(f"Failed to send message to {target_peer.display_name}")
                if target_peer.user_id not in app_state._user_ip_map:
                    print("   No IP address known for target. Wait for their ping/profile.")
                else:
                    print(f"   Target IP: {app_state.get_peer_ip(target_peer.user_id)}")
    
    def _display_dm_history(self, target_peer: Peer) -> None:
        """Display DM history with a user."""
        history = self.message_service.get_dm_history(target_peer.user_id)
        if history:
            print("Chat History:")
            for dm in history:
                display_name = dm.display_name or (dm.from_user.split("@")[0] if "@" in dm.from_user else dm.from_user)
                print(f"{display_name}: {dm.content}")
            print()
        else:
            print("No chat history with this user yet.\n")
    
    def _show_recent_messages(self, user_id: str, count: int = 20) -> None:
        """Show recent messages in a conversation."""
        history = self.message_service.get_dm_history(user_id)
        if history:
            recent = history[-count:] if count else history
            print("\n" + "─" * 40)
            for dm in recent:
                display_name = dm.display_name or (dm.from_user.split("@")[0] if "@" in dm.from_user else dm.from_user)
                print(f"{display_name}: {dm.content}")
            print("─" * 40)
    
    def _add_outgoing_message_to_history(self, target_user_id: str, content: str) -> None:
        """Add outgoing message to DM history."""
        # This is now handled in MessageService.send_direct_message, so this can be removed or left empty.
        pass
    
    def _show_dm_debug_info(self, target_peer: Peer) -> None:
        """Show debug information for DM troubleshooting."""
        print(f"\nDEBUG INFO:")
        print(f"Target UID: {target_peer.user_id}")
        print(f"Your UID: {self.user.user_id}")
        print(f"Target IP: {app_state.get_peer_ip(target_peer.user_id) or 'Not found'}")
        
        conversations = self.message_service.get_dm_conversations()
        print(f"DM conversations: {list(conversations.keys())}")
        
        if target_peer.user_id in conversations:
            history = self.message_service.get_dm_history(target_peer.user_id)
            print(f"Messages with {target_peer.user_id}: {len(history)}")
            for i, dm in enumerate(history):
                print(f"  {i+1}: {dm.content}")
        else:
            print(f"No message history with {target_peer.user_id}")
        print()
        print(f"DM conversations: {list(conversations.keys())}")
        
        if target_peer.user_id in conversations:
            history = self.message_service.get_dm_history(target_peer.user_id)
            print(f"Messages with {target_peer.user_id}: {len(history)}")
            for i, dm in enumerate(history):
                print(f"  {i+1}: {dm.content}")
        else:
            print(f"No message history with {target_peer.user_id}")
        print()
