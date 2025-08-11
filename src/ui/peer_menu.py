"""Peer management UI."""
from typing import List, Optional

from .components import show_separator, format_time_ago, get_choice
from ..models.user import User, Peer
from ..services.user_service import UserService
from ..core.state import app_state


class PeerMenu:
    """UI for viewing and managing peers."""
    
    def __init__(self, user: User, user_service: UserService):
        self.user = user
        self.user_service = user_service
    
    def show_peers(self) -> None:
        """Show peer management interface."""
        while True:
            peers = self.user_service.get_active_peers(self.user.user_id)
            
            if not peers:
                print("\nNo active peers found.\n")
                break

            print("\n==== Active Peers ====")
            self._display_peers(peers)
            print("======================")
            print(f"Total Peers: {len(peers)}")
            
            choice = input("\nChoose an option: [F#] to follow, [U#] to unfollow, [B] to go back\n").strip().upper()
            
            if choice == "B":
                break
            
            if choice.startswith(("F", "U")) and len(choice) > 1:
                try:
                    peer_index = int(choice[1:]) - 1
                    if 0 <= peer_index < len(peers):
                        peer = peers[peer_index]
                        self._handle_follow_unfollow(choice[0], peer)
                    else:
                        print("Invalid peer number.\n")
                except ValueError:
                    print("Invalid option.\n")
            else:
                print("Invalid option.\n")
    
    def _display_peers(self, peers: List[Peer]) -> None:
        """Display list of peers with follow status."""
        for idx, peer in enumerate(peers, start=1):
            is_following = app_state.is_following(peer.user_id)
            following_status = f"You follow {peer.display_name}" if is_following else f"You are not following {peer.display_name}"
            action_key = f"U{idx}" if is_following else f"F{idx}"
            
            print(f"{idx}. {peer.display_name} ({peer.user_id})")
            print(f"{following_status}")
            print(f"Status    : {peer.status}")
            print(f"Last Seen : {format_time_ago(peer.seconds_since_seen)}")
            print(f"Press [{action_key}] to {'Unfollow' if is_following else 'Follow'}\n")
    
    def _handle_follow_unfollow(self, action: str, peer: Peer) -> None:
        """Handle follow/unfollow action."""
        if action == "F":
            success = self.user_service.follow_user(peer.user_id, self.user)
            if success:
                print(f"Successfully Followed {peer.user_id}\n")
            else:
                print(f"Failed to follow {peer.user_id}\n")
        elif action == "U":
            success = self.user_service.unfollow_user(peer.user_id, self.user)
            if success:
                print(f"Successfully Unfollowed {peer.user_id}\n")
            else:
                print(f"Failed to unfollow {peer.user_id}\n")
