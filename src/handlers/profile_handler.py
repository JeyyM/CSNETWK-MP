"""Handler for PROFILE messages."""
import time

from ..models.user import Peer
from ..core.state import app_state


class ProfileHandler:
    """Handles PROFILE messages."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def handle(self, msg: dict, addr: tuple) -> None:
        """Handle a PROFILE message."""
        user_id = msg.get("USER_ID")
        display_name = msg.get("DISPLAY_NAME", "")
        status = msg.get("STATUS", "")
        
        if not user_id:
            if self.verbose:
                print("PROFILE missing USER_ID")
            return
        
        # Create or update peer
        peer = Peer(
            user_id=user_id,
            display_name=display_name,
            status=status,
            ip=addr[0],
            last_seen=time.time()
        )
        
        app_state.add_peer(peer)
        
        if self.verbose:
            print(f"PROFILE from {display_name} ({user_id}) at {addr[0]}")
