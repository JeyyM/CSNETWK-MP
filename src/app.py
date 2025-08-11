"""Main application controller."""
import threading
import time
from typing import Optional

from .models.user import User
from .network.client import NetworkManager
from .network.listener import UDPListener
from .services.user_service import UserService
from .services.message_service import MessageService
from .services.game_service import GameService
from .services.ping_service import PingService
from .services.group_service import GroupService
from .handlers.message_router import MessageRouter
from .ui.main_menu import MainMenu
from .ui.peer_menu import PeerMenu
from .ui.posts_menu import PostsMenu
from .ui.dm_menu import DirectMessageMenu
from .ui.game_menu import GameMenu
from .ui.group_menu import GroupMenu
from .utils.setup import create_user_profile

class LSNPApplication:
    """Main LSNP application controller."""
    
    def __init__(self):
        self.user: Optional[User] = None
        self.network_manager: Optional[NetworkManager] = None
        self.listener: Optional[UDPListener] = None
        self.message_router: Optional[MessageRouter] = None
        
        # Services
        self.user_service: Optional[UserService] = None
        self.message_service: Optional[MessageService] = None
        self.game_service: Optional[GameService] = None
        self.ping_service: Optional[PingService] = None
        self.group_service: Optional[GroupService] = None
        
        # UI Components
        self.main_menu: Optional[MainMenu] = None
        self.peer_menu: Optional[PeerMenu] = None
        self.posts_menu: Optional[PostsMenu] = None
        self.dm_menu: Optional[DirectMessageMenu] = None
        self.game_menu: Optional[GameMenu] = None
        self.group_menu: Optional[GroupMenu] = None
        
        # Background threads
        self.listener_thread: Optional[threading.Thread] = None
        self.running = False
    
    def initialize(self) -> None:
        """Initialize the application."""
        # Create user profile
        self.user = create_user_profile()
        
        # Initialize network layer
        self.network_manager = NetworkManager(self.user.verbose)
        
        # Initialize message router
        self.message_router = MessageRouter(self.network_manager, self.user.verbose)
        
        # Initialize listener
        self.listener = UDPListener(
            self.message_router.route_message,
            self.user.verbose
        )
        
        # Initialize services
        self.user_service = UserService(self.network_manager)
        self.message_service = MessageService(self.network_manager)
        self.game_service = GameService(self.network_manager)
        self.ping_service = PingService(self.network_manager)
        self.group_service = GroupService(self.network_manager)
        
        # Initialize UI components
        self.main_menu = MainMenu(self.user)
        self.peer_menu = PeerMenu(self.user, self.user_service)
        self.posts_menu = PostsMenu(self.user, self.message_service)
        self.dm_menu = DirectMessageMenu(self.user, self.message_service, self.user_service)
        self.game_menu = GameMenu(self.user, self.game_service, self.user_service)
        self.group_menu = GroupMenu(self.user, self.group_service, self.user_service)
    
    def start(self) -> None:
        """Start the application."""
        if not self.user:
            raise RuntimeError("Application not initialized")
        
        self.running = True
        
        # Start UDP listener in background
        self.listener_thread = threading.Thread(
            target=self.listener.start,
            daemon=True
        )
        self.listener_thread.start()
        
        # Give listener time to start
        time.sleep(1)
        
        # Broadcast initial profile
        self.user_service.broadcast_profile(self.user)
        
        # Start ping service
        self.ping_service.start_ping_service(self.user)
        
        # Start main UI loop
        self._main_loop()
    
    def stop(self) -> None:
        """Stop the application."""
        self.running = False
        if self.listener:
            self.listener.stop()
        if self.ping_service:
            self.ping_service.stop_ping_service()
    
    def _main_loop(self) -> None:
        """Main application loop."""
        while self.running:
            try:
                choice = self.main_menu.show()
                
                if choice is None:
                    continue
                
                if choice == "0":
                    self.main_menu.toggle_verbose()
                    # Update network manager verbose setting
                    self.network_manager.verbose = self.user.verbose
                
                elif choice == "1":
                    self.peer_menu.show_peers()
                
                elif choice == "2":
                    self.posts_menu.show_posts_menu()
                
                elif choice == "3":
                    self.dm_menu.show_dm_menu()
                
                elif choice == "4":
                    self.group_menu.show_group_menu()
                
                elif choice == "5":
                    print("File transfer not yet implemented.\n")
                
                elif choice == "6":
                    self.game_menu.show_game_menu()
                
                elif choice == "7":
                    self.main_menu.show_profile()
                    self._show_additional_profile_info()
                
                elif choice == "8":
                    print("\nExiting LSNP...\n")
                    self.stop()
                    break
                
                else:
                    print("That feature is not yet implemented.\n")
            
            except KeyboardInterrupt:
                print("\n\nExiting LSNP...\n")
                self.stop()
                break
            except Exception as e:
                print(f"❌ An error occurred: {e}")
                if self.user and self.user.verbose:
                    import traceback
                    traceback.print_exc()
    
    def _show_additional_profile_info(self) -> None:
        """Show additional profile information."""
        from .core.state import app_state
        
        peers = app_state.get_active_peers()
        conversations = self.message_service.get_dm_conversations()
        groups = self.group_service.get_user_groups(self.user.user_id)
        
        print(f"Profile data stored: {len(peers)} peers")
        print(f"DM conversations: {len(conversations)}")
        print(f"Groups: {len(groups)}")
        
        for user_id, msg_count in conversations.items():
            peer = app_state.get_peer(user_id)
            display_name = peer.display_name if peer else user_id.split("@")[0]
            print(f"  - {display_name} ({user_id}): {msg_count} messages")
        
        if groups:
            print("\nGroup memberships:")
            for group in groups:
                role = "Creator" if group.is_creator(self.user.user_id) else "Member"
                message_count = len(self.group_service.get_group_messages(group.group_id))
                print(f"  - {group.group_name} ({role}): {message_count} messages")
        
        print()


def main() -> None:
    """Main entry point."""
    app = LSNPApplication()
    app.initialize()
    app.start()


if __name__ == "__main__":
    main()
