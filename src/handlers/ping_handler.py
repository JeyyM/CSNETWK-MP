"""Handler for PING messages."""
import time

from ..models.user import Peer
from ..core.state import app_state


class PingHandler:
    """Handles PING messages."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def handle(self, msg: dict, addr: tuple) -> None:
        """Handle a PING message."""
        user_id = msg.get("USER_ID")
        if not user_id:
            if self.verbose:
                print("PING missing USER_ID")
            return
        
        # Update peer table and IP mapping
        now = time.time()
        peer = app_state.get_peer(user_id)
        
        if peer:
            # Update existing peer
            peer.last_seen = now
            peer.ip = addr[0]
        else:
            # Create new peer with minimal info
            peer = Peer(
                user_id=user_id,
                display_name=user_id.split("@")[0] if "@" in user_id else user_id,
                status="",
                ip=addr[0],
                last_seen=now
            )
        
        app_state.add_peer(peer)
        
        if self.verbose:
            print(f"PING from {user_id} at {addr[0]}")
